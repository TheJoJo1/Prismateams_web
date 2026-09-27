"""
Service für die Verwaltung von Label-Vorlagen und Druckaufträgen.

Dieser Service bietet Funktionalität für:
- Erstellung und Verwaltung von Label-Vorlagen
- Dynamische Inhaltsgenerierung für Etiketten
- Druckauftragsverwaltung
- QR-Code und Barcode-Generierung für Etiketten
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import json
import re

from app import db
from app.models.label import LabelTemplate, LabelTemplateElement, LabelPrintJob, LABEL_ELEMENT_TYPES
from app.models.inventory import Product, ProductInstance
from app.models.user import User
from app.utils.qr_code import generate_qr_code_bytes, generate_qr_code


class LabelService:
    """Service für Label-Vorlagen und Druck."""
    
    @staticmethod
    def create_template(
        name: str,
        width_mm: float = 50.0,
        height_mm: float = 30.0,
        unit: str = 'mm',
        description: Optional[str] = None,
        background_color: Optional[str] = None,
        margin_top_mm: float = 2.0,
        margin_right_mm: float = 2.0,
        margin_bottom_mm: float = 2.0,
        margin_left_mm: float = 2.0,
        created_by: Optional[int] = None,
    ) -> LabelTemplate:
        """
        Erstellt eine neue Label-Vorlage.
        
        Args:
            name: Name der Vorlage
            width_mm: Breite in Millimetern
            height_mm: Höhe in Millimetern
            unit: Einheit (mm, cm, inch)
            description: Beschreibung
            background_color: Hintergrundfarbe
            margin_*: Ränder
            created_by: Ersteller-ID
            
        Returns:
            Die erstellte Vorlage
            
        Raises:
            ValueError: Wenn Name bereits existiert
        """
        # Prüfe ob Name bereits existiert
        existing = LabelTemplate.query.filter_by(name=name.strip()).first()
        if existing:
            raise ValueError(f"Label-Vorlage mit Namen '{name}' existiert bereits")
        
        template = LabelTemplate(
            name=name.strip(),
            width_mm=width_mm,
            height_mm=height_mm,
            unit=unit,
            description=description,
            background_color=background_color,
            margin_top_mm=margin_top_mm,
            margin_right_mm=margin_right_mm,
            margin_bottom_mm=margin_bottom_mm,
            margin_left_mm=margin_left_mm,
            created_by=created_by,
            active=True,
        )
        
        db.session.add(template)
        db.session.commit()
        
        return template
    
    @staticmethod
    def get_template(template_id: int) -> Optional[LabelTemplate]:
        """Holt eine Label-Vorlage nach ID."""
        return LabelTemplate.query.get(template_id)
    
    @staticmethod
    def get_all_templates(include_inactive: bool = False) -> List[LabelTemplate]:
        """Holt alle Label-Vorlagen."""
        query = LabelTemplate.query
        if not include_inactive:
            query = query.filter_by(active=True)
        return query.order_by(
            LabelTemplate.name,
        ).all()
    
    @staticmethod
    def update_template(
        template_id: int,
        name: Optional[str] = None,
        width_mm: Optional[float] = None,
        height_mm: Optional[float] = None,
        unit: Optional[str] = None,
        description: Optional[str] = None,
        background_color: Optional[str] = None,
        margin_top_mm: Optional[float] = None,
        margin_right_mm: Optional[float] = None,
        margin_bottom_mm: Optional[float] = None,
        margin_left_mm: Optional[float] = None,
        active: Optional[bool] = None,
        updated_by: Optional[int] = None,
    ) -> LabelTemplate:
        """
        Aktualisiert eine Label-Vorlage.
        
        Args:
            template_id: ID der Vorlage
            ...: Felder die aktualisiert werden sollen
            updated_by: Benutzer-ID der die Änderung durchführt
            
        Returns:
            Die aktualisierte Vorlage
            
        Raises:
            ValueError: Wenn Vorlage nicht existiert oder Name bereits vergeben
        """
        template = LabelTemplate.query.get(template_id)
        if not template:
            raise ValueError(f"Label-Vorlage mit ID {template_id} existiert nicht")
        
        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("Name ist erforderlich")
            # Prüfe ob Name bereits existiert (außer bei sich selbst)
            existing = LabelTemplate.query.filter_by(name=name).first()
            if existing and existing.id != template_id:
                raise ValueError(f"Label-Vorlage mit Namen '{name}' existiert bereits")
            template.name = name
        
        if width_mm is not None:
            template.width_mm = width_mm
        if height_mm is not None:
            template.height_mm = height_mm
        if unit is not None:
            template.unit = unit
        if description is not None:
            template.description = description
        if background_color is not None:
            template.background_color = background_color
        if margin_top_mm is not None:
            template.margin_top_mm = margin_top_mm
        if margin_right_mm is not None:
            template.margin_right_mm = margin_right_mm
        if margin_bottom_mm is not None:
            template.margin_bottom_mm = margin_bottom_mm
        if margin_left_mm is not None:
            template.margin_left_mm = margin_left_mm
        if active is not None:
            template.active = active
        
        template.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return template
    
    @staticmethod
    def delete_template(template_id: int, deleted_by: Optional[int] = None) -> None:
        """
        Löscht eine Label-Vorlage.
        
        Args:
            template_id: ID der Vorlage
            deleted_by: Benutzer-ID der die Löschung durchführt
            
        Raises:
            ValueError: Wenn Vorlage nicht existiert
        """
        template = LabelTemplate.query.get(template_id)
        if not template:
            raise ValueError(f"Label-Vorlage mit ID {template_id} existiert nicht")
        
        # Lösche zugehörige Elemente
        LabelTemplateElement.query.filter_by(template_id=template_id).delete()
        
        db.session.delete(template)
        db.session.commit()
    
    @staticmethod
    def add_element(
        template_id: int,
        element_type: str,
        x_mm: float = 0.0,
        y_mm: float = 0.0,
        width_mm: float = 20.0,
        height_mm: float = 10.0,
        content: Optional[str] = None,
        font_family: str = 'Arial',
        font_size_pt: float = 10.0,
        font_weight: str = 'normal',
        font_style: str = 'normal',
        text_color: str = '#000000',
        text_align: str = 'left',
        border_width_mm: float = 0.0,
        border_color: Optional[str] = None,
        border_radius_mm: float = 0.0,
        background_color: Optional[str] = None,
        rotation_degrees: float = 0.0,
        z_index: int = 0,
        configuration: Optional[Dict[str, Any]] = None,
    ) -> LabelTemplateElement:
        """
        Fügt ein Element zu einer Label-Vorlage hinzu.
        
        Args:
            template_id: ID der Vorlage
            element_type: Typ des Elements
            x_mm, y_mm: Position
            width_mm, height_mm: Größe
            content: Inhalt
            ...: Weitere Element-Eigenschaften
            configuration: Zusätzliche Konfiguration als Dict
            
        Returns:
            Das erstellte Element
            
        Raises:
            ValueError: Wenn Vorlage nicht existiert oder Typ ungültig
        """
        template = LabelTemplate.query.get(template_id)
        if not template:
            raise ValueError(f"Label-Vorlage mit ID {template_id} existiert nicht")
        
        if element_type not in LABEL_ELEMENT_TYPES:
            raise ValueError(f"Ungültiger Element-Typ: {element_type}")
        
        element = LabelTemplateElement(
            template_id=template_id,
            element_type=element_type,
            x_mm=x_mm,
            y_mm=y_mm,
            width_mm=width_mm,
            height_mm=height_mm,
            content=content,
            font_family=font_family,
            font_size_pt=font_size_pt,
            font_weight=font_weight,
            font_style=font_style,
            text_color=text_color,
            text_align=text_align,
            border_width_mm=border_width_mm,
            border_color=border_color,
            border_radius_mm=border_radius_mm,
            background_color=background_color,
            rotation_degrees=rotation_degrees,
            z_index=z_index,
        )
        
        if configuration:
            element.set_configuration(configuration)
        
        db.session.add(element)
        db.session.commit()
        
        return element
    
    @staticmethod
    def update_element(
        element_id: int,
        element_type: Optional[str] = None,
        x_mm: Optional[float] = None,
        y_mm: Optional[float] = None,
        width_mm: Optional[float] = None,
        height_mm: Optional[float] = None,
        content: Optional[str] = None,
        font_family: Optional[str] = None,
        font_size_pt: Optional[float] = None,
        font_weight: Optional[str] = None,
        font_style: Optional[str] = None,
        text_color: Optional[str] = None,
        text_align: Optional[str] = None,
        border_width_mm: Optional[float] = None,
        border_color: Optional[str] = None,
        border_radius_mm: Optional[float] = None,
        background_color: Optional[str] = None,
        rotation_degrees: Optional[float] = None,
        z_index: Optional[int] = None,
        configuration: Optional[Dict[str, Any]] = None,
    ) -> LabelTemplateElement:
        """
        Aktualisiert ein Label-Element.
        
        Args:
            element_id: ID des Elements
            ...: Felder die aktualisiert werden sollen
            configuration: Zusätzliche Konfiguration als Dict
            
        Returns:
            Das aktualisierte Element
            
        Raises:
            ValueError: Wenn Element nicht existiert oder Typ ungültig
        """
        element = LabelTemplateElement.query.get(element_id)
        if not element:
            raise ValueError(f"Label-Element mit ID {element_id} existiert nicht")
        
        if element_type is not None:
            if element_type not in LABEL_ELEMENT_TYPES:
                raise ValueError(f"Ungültiger Element-Typ: {element_type}")
            element.element_type = element_type
        
        if x_mm is not None:
            element.x_mm = x_mm
        if y_mm is not None:
            element.y_mm = y_mm
        if width_mm is not None:
            element.width_mm = width_mm
        if height_mm is not None:
            element.height_mm = height_mm
        if content is not None:
            element.content = content
        if font_family is not None:
            element.font_family = font_family
        if font_size_pt is not None:
            element.font_size_pt = font_size_pt
        if font_weight is not None:
            element.font_weight = font_weight
        if font_style is not None:
            element.font_style = font_style
        if text_color is not None:
            element.text_color = text_color
        if text_align is not None:
            element.text_align = text_align
        if border_width_mm is not None:
            element.border_width_mm = border_width_mm
        if border_color is not None:
            element.border_color = border_color
        if border_radius_mm is not None:
            element.border_radius_mm = border_radius_mm
        if background_color is not None:
            element.background_color = background_color
        if rotation_degrees is not None:
            element.rotation_degrees = rotation_degrees
        if z_index is not None:
            element.z_index = z_index
        
        if configuration is not None:
            element.set_configuration(configuration)
        
        element.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return element
    
    @staticmethod
    def delete_element(element_id: int) -> None:
        """
        Löscht ein Label-Element.
        
        Args:
            element_id: ID des Elements
            
        Raises:
            ValueError: Wenn Element nicht existiert
        """
        element = LabelTemplateElement.query.get(element_id)
        if not element:
            raise ValueError(f"Label-Element mit ID {element_id} existiert nicht")
        
        db.session.delete(element)
        db.session.commit()
    
    @staticmethod
    def render_template(
        template: LabelTemplate,
        product: Optional[Product] = None,
        instance: Optional[ProductInstance] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Rendert eine Label-Vorlage mit dynamischen Daten.
        
        Ersetzt Platzhalter in den Element-Inhalten mit tatsächlichen Daten.
        
        Args:
            template: Die Label-Vorlage
            product: Das Produkt (optional)
            instance: Die Produktinstanz (optional)
            data: Zusätzliche Daten als Dictionary
            
        Returns:
            Dictionary mit gerenderten Elementen und Metadaten
        """
        data = data or {}
        
        rendered_elements = []
        for element in template.elements:
            rendered_content = LabelService._render_element_content(
                element,
                product=product,
                instance=instance,
                data=data,
            )
            rendered_elements.append({
                'id': element.id,
                'element_type': element.element_type,
                'x_mm': element.x_mm,
                'y_mm': element.y_mm,
                'width_mm': element.width_mm,
                'height_mm': element.height_mm,
                'content': rendered_content,
                'font_family': element.font_family,
                'font_size_pt': element.font_size_pt,
                'font_weight': element.font_weight,
                'font_style': element.font_style,
                'text_color': element.text_color,
                'text_align': element.text_align,
                'border_width_mm': element.border_width_mm,
                'border_color': element.border_color,
                'border_radius_mm': element.border_radius_mm,
                'background_color': element.background_color,
                'rotation_degrees': element.rotation_degrees,
                'z_index': element.z_index,
                'configuration': element.get_configuration(),
            })
        
        return {
            'template_id': template.id,
            'template_name': template.name,
            'width_mm': template.width_mm,
            'height_mm': template.height_mm,
            'unit': template.unit,
            'background_color': template.background_color,
            'margin_top_mm': template.margin_top_mm,
            'margin_right_mm': template.margin_right_mm,
            'margin_bottom_mm': template.margin_bottom_mm,
            'margin_left_mm': template.margin_left_mm,
            'elements': rendered_elements,
        }
    
    @staticmethod
    def _render_element_content(
        element: LabelTemplateElement,
        product: Optional[Product] = None,
        instance: Optional[ProductInstance] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Rendert den Inhalt eines einzelnen Elements mit Platzhalter-Ersetzung.
        
        Args:
            element: Das Label-Element
            product: Das Produkt
            instance: Die Produktinstanz
            data: Zusätzliche Daten
            
        Returns:
            Der gerenderte Inhalt
        """
        if not element.content:
            return ''
        
        content = element.content
        data = data or {}
        
        # Produkt-Daten
        if product:
            replacements = {
                '{{product.name}}': product.name or '',
                '{{product.description}}': product.description or '',
                '{{product.category}}': product.category or '',
                '{{product.serial_number}}': product.serial_number or '',
                '{{product.id}}': str(product.id),
            }
            for placeholder, value in replacements.items():
                content = content.replace(placeholder, value)
        
        # Instanz-Daten
        if instance:
            replacements = {
                '{{instance.inventory_number}}': instance.inventory_number or '',
                '{{instance.serial_number}}': instance.serial_number or '',
                '{{instance.dguv_id}}': instance.dguv_id or '',
                '{{instance.status}}': instance.status or '',
                '{{instance.color}}': instance.effective_color or (instance.color.name if instance.color else ''),
                '{{instance.location}}': instance.location or '',
                '{{instance.id}}': str(instance.id),
            }
            for placeholder, value in replacements.items():
                content = content.replace(placeholder, value)
        
        # Datum
        replacements = {
            '{{date}}': datetime.now().strftime('%Y-%m-%d'),
            '{{date.long}}': datetime.now().strftime('%d. %B %Y'),
            '{{date.short}}': datetime.now().strftime('%d.%m.%Y'),
            '{{time}}': datetime.now().strftime('%H:%M:%S'),
        }
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)
        
        # Benutzerdefinierte Daten
        for key, value in data.items():
            placeholder = f'{{{{{key}}}}}'
            content = content.replace(placeholder, str(value))
        
        return content
    
    @staticmethod
    def generate_qr_code_data(
        product: Optional[Product] = None,
        instance: Optional[ProductInstance] = None,
        custom_data: Optional[str] = None,
    ) -> str:
        """
        Generiert die Daten für einen QR-Code.
        
        Args:
            product: Das Produkt
            instance: Die Produktinstanz
            custom_data: Benutzerdefinierte Daten
            
        Returns:
            Die QR-Code-Daten als String
        """
        if custom_data:
            return custom_data
        
        if instance:
            return f"INSTANCE-{instance.id}"
        
        if product:
            return f"PROD-{product.id}"
        
        return "PRISMATEAMS-LABEL"
    
    @staticmethod
    def generate_barcode_data(
        product: Optional[Product] = None,
        instance: Optional[ProductInstance] = None,
        custom_data: Optional[str] = None,
    ) -> str:
        """
        Generiert die Daten für einen Barcode.
        
        Args:
            product: Das Produkt
            instance: Die Produktinstanz
            custom_data: Benutzerdefinierte Daten
            
        Returns:
            Die Barcode-Daten als String
        """
        if custom_data:
            return custom_data
        
        if instance:
            return instance.inventory_number or instance.serial_number or str(instance.id)
        
        if product:
            return product.serial_number or str(product.id)
        
        return "PRISMATEAMS"
    
    @staticmethod
    def create_print_job(
        template_id: Optional[int] = None,
        product_id: Optional[int] = None,
        instance_ids: Optional[List[int]] = None,
        label_count: int = 1,
        copies_per_label: int = 1,
        created_by: Optional[int] = None,
    ) -> LabelPrintJob:
        """
        Erstellt einen neuen Druckauftrag.
        
        Args:
            template_id: ID der Label-Vorlage
            product_id: ID des Produkts
            instance_ids: Liste der Instanz-IDs
            label_count: Anzahl der Etiketten
            copies_per_label: Kopien pro Etikett
            created_by: Ersteller-ID
            
        Returns:
            Der erstellte Druckauftrag
        """
        # Generiere Job-Nummer
        import secrets
        import string
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
        job_number = f"LABEL-{timestamp}-{random_part}"
        
        job = LabelPrintJob(
            job_number=job_number,
            template_id=template_id,
            product_id=product_id,
            instance_ids=json.dumps(instance_ids) if instance_ids else None,
            label_count=label_count,
            copies_per_label=copies_per_label,
            created_by=created_by,
            status='pending',
        )
        
        db.session.add(job)
        db.session.commit()
        
        return job
    
    @staticmethod
    def get_print_job(job_id: int) -> Optional[LabelPrintJob]:
        """Holt einen Druckauftrag nach ID."""
        return LabelPrintJob.query.get(job_id)
    
    @staticmethod
    def get_print_jobs(
        status: Optional[str] = None,
        created_by: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[LabelPrintJob]:
        """
        Holt Druckaufträge mit optionalem Filter.
        
        Args:
            status: Filter nach Status
            created_by: Filter nach Ersteller
            limit: Maximale Anzahl Ergebnisse
            offset: Offset für Pagination
            
        Returns:
            Liste der Druckaufträge
        """
        query = LabelPrintJob.query
        
        if status:
            query = query.filter_by(status=status)
        if created_by:
            query = query.filter_by(created_by=created_by)
        
        query = query.order_by(LabelPrintJob.created_at.desc())
        
        return query.offset(offset).limit(limit).all()
    
    @staticmethod
    def update_print_job_status(
        job_id: int,
        status: str,
        error_message: Optional[str] = None,
    ) -> LabelPrintJob:
        """
        Aktualisiert den Status eines Druckauftrags.
        
        Args:
            job_id: ID des Druckauftrags
            status: Neuer Status
            error_message: Fehlermeldung (falls Status = 'failed')
            
        Returns:
            Der aktualisierte Druckauftrag
            
        Raises:
            ValueError: Wenn Druckauftrag nicht existiert
        """
        job = LabelPrintJob.query.get(job_id)
        if not job:
            raise ValueError(f"Druckauftrag mit ID {job_id} existiert nicht")
        
        valid_statuses = {'pending', 'printing', 'completed', 'failed'}
        if status not in valid_statuses:
            raise ValueError(f"Ungültiger Status: {status}")
        
        job.status = status
        job.error_message = error_message
        
        if status in {'completed', 'failed'}:
            job.completed_at = datetime.utcnow()
        
        db.session.commit()
        
        return job
    
    @staticmethod
    def get_available_placeholders() -> Dict[str, str]:
        """
        Gibt eine Liste der verfügbaren Platzhalter zurück.
        
        Returns:
            Dictionary mit Platzhaltern und Beschreibungen
        """
        return {
            # Produkt-Platzhalter
            'product.name': 'Name des Produkts',
            'product.description': 'Beschreibung des Produkts',
            'product.category': 'Kategorie des Produkts',
            'product.serial_number': 'Seriennummer des Produkts',
            'product.id': 'ID des Produkts',
            
            # Instanz-Platzhalter
            'instance.inventory_number': 'Inventarnummer der Instanz',
            'instance.serial_number': 'Seriennummer der Instanz',
            'instance.dguv_id': 'DGUV-ID der Instanz',
            'instance.status': 'Status der Instanz',
            'instance.color': 'Farbe der Instanz',
            'instance.location': 'Standort der Instanz',
            'instance.id': 'ID der Instanz',
            
            # Datum/Zeit-Platzhalter
            'date': 'Aktuelles Datum (YYYY-MM-DD)',
            'date.long': 'Aktuelles Datum (lang, z.B. 01. Januar 2024)',
            'date.short': 'Aktuelles Datum (kurz, z.B. 01.01.2024)',
            'time': 'Aktuelle Uhrzeit (HH:MM:SS)',
        }
    
    @staticmethod
    def generate_label_pdf(
        template: LabelTemplate,
        product: Optional[Product] = None,
        instance: Optional[ProductInstance] = None,
        data: Optional[Dict[str, Any]] = None,
        output_format: str = 'pdf',
    ) -> bytes:
        """
        Generiert ein Label als PDF.
        
        Args:
            template: Die Label-Vorlage
            product: Das Produkt
            instance: Die Produktinstanz
            data: Zusätzliche Daten
            output_format: Ausgabeformat ('pdf' oder 'png')
            
        Returns:
            Die generierten Daten als Bytes
        """
        # Rendere die Vorlage
        rendered = LabelService.render_template(
            template,
            product=product,
            instance=instance,
            data=data,
        )
        
        # Hier würde die tatsächliche PDF-Generierung stattfinden
        # Für den MVP geben wir ein leeres PDF zurück
        # In einer echten Implementierung würde man z.B. ReportLab oder WeasyPrint verwenden
        
        from io import BytesIO
        from reportlab.lib.pagesizes import mm
        from reportlab.pdfgen import canvas
        
        # Erstelle ein PDF mit den Abmessungen der Vorlage
        width_pt = template.width_mm * 2.83465  # mm to pt
        height_pt = template.height_mm * 2.83465  # mm to pt
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=(width_pt, height_pt))
        
        # Hintergrund
        if template.background_color:
            c.setFillColor(LabelService._hex_to_rgb(template.background_color))
            c.rect(0, 0, width_pt, height_pt, fill=1, stroke=0)
        
        # Elemente zeichnen
        for elem in rendered['elements']:
            # Position berechnen (mm zu pt)
            x_pt = elem['x_mm'] * 2.83465
            y_pt = height_pt - (elem['y_mm'] * 2.83465) - (elem['height_mm'] * 2.83465)
            width_pt = elem['width_mm'] * 2.83465
            height_pt = elem['height_mm'] * 2.83465
            
            # Hintergrund des Elements
            if elem.get('background_color'):
                c.setFillColor(LabelService._hex_to_rgb(elem['background_color']))
                c.rect(x_pt, y_pt, width_pt, height_pt, fill=1, stroke=0)
            
            # Text zeichnen
            if elem['element_type'] in ['text', 'product_name', 'product_category', 'product_serial', 
                                       'instance_inventory_number', 'instance_serial_number', 
                                       'instance_dguv_id', 'instance_status', 'instance_color',
                                       'instance_location', 'date', 'custom_field']:
                c.setFillColor(LabelService._hex_to_rgb(elem['text_color']))
                c.setFont(elem['font_family'], elem['font_size_pt'])
                
                # Text-Ausrichtung
                text_x = x_pt
                if elem['text_align'] == 'center':
                    text_x = x_pt + (width_pt / 2)
                elif elem['text_align'] == 'right':
                    text_x = x_pt + width_pt
                
                c.drawString(text_x, y_pt, elem['content'])
            
            # QR-Code
            elif elem['element_type'] == 'qr_code':
                qr_data = LabelService.generate_qr_code_data(
                    product=product,
                    instance=instance,
                    custom_data=elem.get('content'),
                )
                qr_bytes = generate_qr_code_bytes(qr_data, box_size=1, border=0)
                # QR-Code in PDF einbetten (vereinfacht)
                # In einer echten Implementierung würde man die QR-Code-Bytes hier einbetten
                pass
            
            # Barcode
            elif elem['element_type'] == 'barcode':
                barcode_data = LabelService.generate_barcode_data(
                    product=product,
                    instance=instance,
                    custom_data=elem.get('content'),
                )
                # Barcode generieren (vereinfacht)
                # In einer echten Implementierung würde man eine Barcode-Bibliothek verwenden
                pass
        
        c.save()
        buffer.seek(0)
        
        return buffer.getvalue()
    
    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
        """
        Konvertiert eine Hex-Farbe in RGB-Werte (0-1).
        
        Args:
            hex_color: Hex-Farbe (z.B. "#FF0000")
            
        Returns:
            Tuple mit RGB-Werten (0-1)
        """
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join([c * 2 for c in hex_color])
        if len(hex_color) != 6:
            return (0, 0, 0)
        
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        
        return (r, g, b)
