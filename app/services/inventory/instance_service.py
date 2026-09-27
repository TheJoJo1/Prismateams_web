"""
Service für die Verwaltung von Produktinstanzen (individuelle Exemplare).

Dieser Service bietet CRUD-Operationen und Business-Logik für ProductInstance-Objekte.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import or_, and_

from app import db
from app.models.inventory import Product, ProductInstance, ProductInstanceStatusHistory, InventoryColor
from app.models.user import User


# Gültige Status für Produktinstanzen
VALID_INSTANCE_STATUSES = {
    'available',      # Verfügbar
    'borrowed',       # Ausgeliehen
    'defective',      # Defekt
    'in_repair',      # In Reparatur
    'lost',           # Verloren
    'retired',        # Außer Betrieb
}

# Standard-Sortierung für Status
STATUS_SORT_ORDER = {
    'available': 0,
    'borrowed': 1,
    'in_repair': 2,
    'defective': 3,
    'lost': 4,
    'retired': 5,
}


class InstanceService:
    """Service für Produktinstanz-Verwaltung."""
    
    @staticmethod
    def create_instance(
        product_id: int,
        inventory_number: Optional[str] = None,
        serial_number: Optional[str] = None,
        status: str = 'available',
        dguv_enabled: bool = False,
        dguv_id: Optional[str] = None,
        color_id: Optional[int] = None,
        color_override: Optional[str] = None,
        location: Optional[str] = None,
        assigned_user_id: Optional[int] = None,
        notes: Optional[str] = None,
        created_by: Optional[int] = None,
    ) -> ProductInstance:
        """
        Erstellt eine neue Produktinstanz.
        
        Args:
            product_id: ID des übergeordneten Produkts
            inventory_number: Interne Inventarnummer
            serial_number: Hersteller-Seriennummer
            status: Status der Instanz
            dguv_enabled: Ob DGUV-relevant
            dguv_id: DGUV-ID
            color_id: ID der Farbe aus inventory_colors
            color_override: Direkte Hex-Farbe
            location: Standort
            assigned_user_id: Zugewiesener Benutzer
            notes: Notizen
            created_by: Ersteller-ID
            
        Returns:
            Die erstellte Produktinstanz
            
        Raises:
            ValueError: Wenn das Produkt nicht existiert oder Status ungültig
        """
        # Validierung
        product = Product.query.get(product_id)
        if not product:
            raise ValueError(f"Produkt mit ID {product_id} existiert nicht")
        
        if status not in VALID_INSTANCE_STATUSES:
            raise ValueError(f"Ungültiger Status: {status}. Erlaubt: {', '.join(VALID_INSTANCE_STATUSES)}")
        
        # Prüfe ob Farbe existiert
        if color_id:
            color = InventoryColor.query.get(color_id)
            if not color:
                raise ValueError(f"Farbe mit ID {color_id} existiert nicht")
        
        # Prüfe ob Benutzer existiert
        if assigned_user_id:
            user = User.query.get(assigned_user_id)
            if not user:
                raise ValueError(f"Benutzer mit ID {assigned_user_id} existiert nicht")
        
        # Erstelle Instanz
        instance = ProductInstance(
            product_id=product_id,
            inventory_number=inventory_number,
            serial_number=serial_number,
            status=status,
            dguv_enabled=dguv_enabled,
            dguv_id=dguv_id,
            color_id=color_id,
            color_override=color_override,
            location=location,
            assigned_user_id=assigned_user_id,
            notes=notes,
            created_by=created_by or product.created_by,
            active=True,
        )
        
        db.session.add(instance)
        db.session.commit()
        
        # Status-Historie hinzufügen
        InstanceService._add_status_history(
            instance_id=instance.id,
            old_status=None,
            new_status=status,
            reason='Erstellung',
            changed_by=created_by or product.created_by,
        )
        
        return instance
    
    @staticmethod
    def get_instance(instance_id: int) -> Optional[ProductInstance]:
        """Holt eine Produktinstanz nach ID."""
        return ProductInstance.query.get(instance_id)
    
    @staticmethod
    def get_instances_by_product(product_id: int, include_inactive: bool = False) -> List[ProductInstance]:
        """Holt alle Instanzen eines Produkts."""
        query = ProductInstance.query.filter_by(product_id=product_id)
        if not include_inactive:
            query = query.filter_by(active=True)
        return query.order_by(
            STATUS_SORT_ORDER.get(ProductInstance.status, 99),
            ProductInstance.inventory_number,
            ProductInstance.serial_number,
            ProductInstance.id,
        ).all()
    
    @staticmethod
    def get_active_instances_by_product(product_id: int) -> List[ProductInstance]:
        """Holt alle aktiven Instanzen eines Produkts."""
        return InstanceService.get_instances_by_product(product_id, include_inactive=False)
    
    @staticmethod
    def update_instance(
        instance_id: int,
        inventory_number: Optional[str] = None,
        serial_number: Optional[str] = None,
        status: Optional[str] = None,
        dguv_enabled: Optional[bool] = None,
        dguv_id: Optional[str] = None,
        color_id: Optional[int] = None,
        color_override: Optional[str] = None,
        location: Optional[str] = None,
        assigned_user_id: Optional[int] = None,
        notes: Optional[str] = None,
        active: Optional[bool] = None,
        updated_by: Optional[int] = None,
    ) -> ProductInstance:
        """
        Aktualisiert eine Produktinstanz.
        
        Args:
            instance_id: ID der zu aktualisierenden Instanz
            ...: Felder die aktualisiert werden sollen
            updated_by: Benutzer-ID der die Änderung durchführt
            
        Returns:
            Die aktualisierte Produktinstanz
            
        Raises:
            ValueError: Wenn Instanz nicht existiert oder Status ungültig
        """
        instance = ProductInstance.query.get(instance_id)
        if not instance:
            raise ValueError(f"Instanz mit ID {instance_id} existiert nicht")
        
        # Validierung
        if status is not None and status not in VALID_INSTANCE_STATUSES:
            raise ValueError(f"Ungültiger Status: {status}")
        
        if color_id is not None:
            color = InventoryColor.query.get(color_id)
            if not color:
                raise ValueError(f"Farbe mit ID {color_id} existiert nicht")
        
        if assigned_user_id is not None:
            user = User.query.get(assigned_user_id)
            if not user:
                raise ValueError(f"Benutzer mit ID {assigned_user_id} existiert nicht")
        
        # Speichere alten Status für Historie
        old_status = instance.status
        
        # Aktualisiere Felder
        if inventory_number is not None:
            instance.inventory_number = inventory_number
        if serial_number is not None:
            instance.serial_number = serial_number
        if status is not None:
            instance.status = status
        if dguv_enabled is not None:
            instance.dguv_enabled = dguv_enabled
        if dguv_id is not None:
            instance.dguv_id = dguv_id
        if color_id is not None:
            instance.color_id = color_id
        if color_override is not None:
            instance.color_override = color_override
        if location is not None:
            instance.location = location
        if assigned_user_id is not None:
            instance.assigned_user_id = assigned_user_id
        if notes is not None:
            instance.notes = notes
        if active is not None:
            instance.active = active
        
        instance.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Status-Historie hinzufügen wenn Status geändert wurde
        if status is not None and status != old_status:
            InstanceService._add_status_history(
                instance_id=instance_id,
                old_status=old_status,
                new_status=status,
                reason='Manuelle Änderung',
                changed_by=updated_by,
            )
        
        return instance
    
    @staticmethod
    def deactivate_instance(instance_id: int, reason: Optional[str] = None, deleted_by: Optional[int] = None) -> ProductInstance:
        """
        Deaktiviert eine Produktinstanz (Soft Delete).
        
        Args:
            instance_id: ID der zu deaktivierenden Instanz
            reason: Grund für die Deaktivierung
            deleted_by: Benutzer-ID der die Deaktivierung durchführt
            
        Returns:
            Die deaktivierte Produktinstanz
            
        Raises:
            ValueError: Wenn Instanz nicht existiert
        """
        instance = ProductInstance.query.get(instance_id)
        if not instance:
            raise ValueError(f"Instanz mit ID {instance_id} existiert nicht")
        
        old_status = instance.status
        instance.active = False
        instance.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Status-Historie hinzufügen
        InstanceService._add_status_history(
            instance_id=instance_id,
            old_status=old_status,
            new_status='retired',
            reason=reason or 'Deaktiviert',
            changed_by=deleted_by,
        )
        
        return instance
    
    @staticmethod
    def change_status(
        instance_id: int,
        new_status: str,
        reason: Optional[str] = None,
        changed_by: Optional[int] = None,
    ) -> ProductInstance:
        """
        Ändert den Status einer Produktinstanz.
        
        Args:
            instance_id: ID der Instanz
            new_status: Neuer Status
            reason: Grund für die Statusänderung
            changed_by: Benutzer-ID der die Änderung durchführt
            
        Returns:
            Die aktualisierte Produktinstanz
            
        Raises:
            ValueError: Wenn Instanz nicht existiert oder Status ungültig
        """
        if new_status not in VALID_INSTANCE_STATUSES:
            raise ValueError(f"Ungültiger Status: {new_status}")
        
        instance = ProductInstance.query.get(instance_id)
        if not instance:
            raise ValueError(f"Instanz mit ID {instance_id} existiert nicht")
        
        old_status = instance.status
        instance.status = new_status
        instance.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Status-Historie hinzufügen
        InstanceService._add_status_history(
            instance_id=instance_id,
            old_status=old_status,
            new_status=new_status,
            reason=reason or f'Statusänderung: {old_status} -> {new_status}',
            changed_by=changed_by,
        )
        
        return instance
    
    @staticmethod
    def delete_instance(instance_id: int, deleted_by: Optional[int] = None) -> None:
        """
        Löscht eine Produktinstanz physisch aus der Datenbank.
        
        ACHTUNG: Dies entfernt die Instanz dauerhaft. Soft Delete (deactivate_instance)
        sollte bevorzugt werden.
        
        Args:
            instance_id: ID der zu löschenden Instanz
            deleted_by: Benutzer-ID der die Löschung durchführt
            
        Raises:
            ValueError: Wenn Instanz nicht existiert oder aktiv ausgeliehen ist
        """
        instance = ProductInstance.query.get(instance_id)
        if not instance:
            raise ValueError(f"Instanz mit ID {instance_id} existiert nicht")
        
        # Prüfe ob Instanz ausgeliehen ist
        if instance.status == 'borrowed':
            raise ValueError("Instanz kann nicht gelöscht werden, da sie noch ausgegeben ist")
        
        # Lösche zugehörige Historie
        ProductInstanceStatusHistory.query.filter_by(instance_id=instance_id).delete()
        
        db.session.delete(instance)
        db.session.commit()
    
    @staticmethod
    def search_instances(
        product_id: Optional[int] = None,
        inventory_number: Optional[str] = None,
        serial_number: Optional[str] = None,
        status: Optional[str] = None,
        dguv_id: Optional[str] = None,
        color_id: Optional[int] = None,
        location: Optional[str] = None,
        assigned_user_id: Optional[int] = None,
        search_query: Optional[str] = None,
        include_inactive: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Sucht nach Produktinstanzen mit verschiedenen Filtern.
        
        Args:
            product_id: Filter nach Produkt-ID
            inventory_number: Filter nach Inventarnummer
            serial_number: Filter nach Seriennummer
            status: Filter nach Status
            dguv_id: Filter nach DGUV-ID
            color_id: Filter nach Farb-ID
            location: Filter nach Standort
            assigned_user_id: Filter nach zugewiesenem Benutzer
            search_query: Freitextsuche in Inventarnummer, Seriennummer, DGUV-ID
            include_inactive: Inklusive deaktivierter Instanzen
            limit: Maximale Anzahl Ergebnisse
            offset: Offset für Pagination
            
        Returns:
            Dict mit 'items' (Liste der Instanzen) und 'total' (Gesamtanzahl)
        """
        query = ProductInstance.query
        
        # Basis-Filter
        if not include_inactive:
            query = query.filter_by(active=True)
        
        # Produkt-Filter
        if product_id is not None:
            query = query.filter_by(product_id=product_id)
        
        # Status-Filter
        if status is not None:
            query = query.filter_by(status=status)
        
        # Textsuche
        if search_query:
            search_filters = []
            if inventory_number is None:
                search_filters.append(ProductInstance.inventory_number.ilike(f'%{search_query}%'))
            if serial_number is None:
                search_filters.append(ProductInstance.serial_number.ilike(f'%{search_query}%'))
            if dguv_id is None:
                search_filters.append(ProductInstance.dguv_id.ilike(f'%{search_query}%'))
            if search_filters:
                query = query.filter(or_(*search_filters))
        
        # Spezifische Filter
        if inventory_number is not None:
            query = query.filter(ProductInstance.inventory_number.ilike(f'%{inventory_number}%'))
        if serial_number is not None:
            query = query.filter(ProductInstance.serial_number.ilike(f'%{serial_number}%'))
        if dguv_id is not None:
            query = query.filter(ProductInstance.dguv_id.ilike(f'%{dguv_id}%'))
        if color_id is not None:
            query = query.filter_by(color_id=color_id)
        if location is not None:
            query = query.filter(ProductInstance.location.ilike(f'%{location}%'))
        if assigned_user_id is not None:
            query = query.filter_by(assigned_user_id=assigned_user_id)
        
        # Sortierung
        query = query.order_by(
            STATUS_SORT_ORDER.get(ProductInstance.status, 99),
            ProductInstance.inventory_number,
            ProductInstance.serial_number,
            ProductInstance.id,
        )
        
        # Zählung und Pagination
        total = query.count()
        items = query.offset(offset).limit(limit).all()
        
        return {
            'items': items,
            'total': total,
            'limit': limit,
            'offset': offset,
        }
    
    @staticmethod
    def get_instance_counts_by_status(product_id: int) -> Dict[str, int]:
        """
        Gibt die Anzahl der Instanzen pro Status für ein Produkt zurück.
        
        Args:
            product_id: ID des Produkts
            
        Returns:
            Dict mit Status als Key und Anzahl als Value
        """
        instances = ProductInstance.query.filter_by(
            product_id=product_id,
            active=True,
        ).all()
        
        counts = {s: 0 for s in VALID_INSTANCE_STATUSES}
        for instance in instances:
            counts[instance.status] = counts.get(instance.status, 0) + 1
        
        return counts
    
    @staticmethod
    def _add_status_history(
        instance_id: int,
        old_status: Optional[str],
        new_status: str,
        reason: Optional[str] = None,
        changed_by: Optional[int] = None,
    ) -> ProductInstanceStatusHistory:
        """
        Fügt einen Eintrag in die Status-Historie hinzu.
        
        Args:
            instance_id: ID der Instanz
            old_status: Alter Status (kann None sein bei Erstellung)
            new_status: Neuer Status
            reason: Grund für die Änderung
            changed_by: Benutzer-ID der die Änderung durchführt
            
        Returns:
            Der erstellte Historie-Eintrag
        """
        history = ProductInstanceStatusHistory(
            instance_id=instance_id,
            old_status=old_status,
            new_status=new_status,
            reason=reason,
            changed_by=changed_by,
            changed_at=datetime.utcnow(),
        )
        
        db.session.add(history)
        db.session.commit()
        
        return history
    
    @staticmethod
    def get_status_history(instance_id: int, limit: int = 50) -> List[ProductInstanceStatusHistory]:
        """
        Holt die Status-Historie einer Instanz.
        
        Args:
            instance_id: ID der Instanz
            limit: Maximale Anzahl Einträge
            
        Returns:
            Liste der Historie-Einträge, sortiert nach Datum (neueste zuerst)
        """
        return ProductInstanceStatusHistory.query.filter_by(
            instance_id=instance_id,
        ).order_by(
            ProductInstanceStatusHistory.changed_at.desc(),
        ).limit(limit).all()


class ColorService:
    """Service für Farbverwaltung."""
    
    @staticmethod
    def create_color(
        name: str,
        color_hex: str,
        description: Optional[str] = None,
        sort_order: int = 0,
        created_by: Optional[int] = None,
    ) -> InventoryColor:
        """
        Erstellt eine neue Farbe.
        
        Args:
            name: Name der Farbe
            color_hex: Hex-Farbwert (z.B. "#FF0000")
            description: Beschreibung
            sort_order: Sortierordnung
            created_by: Ersteller-ID
            
        Returns:
            Die erstellte Farbe
            
        Raises:
            ValueError: Wenn Name oder Farbe bereits existiert
        """
        # Validierung
        if not name or not name.strip():
            raise ValueError("Farbname ist erforderlich")
        
        if not color_hex or not color_hex.strip():
            raise ValueError("Hex-Farbwert ist erforderlich")
        
        # Prüfe ob Name bereits existiert
        existing = InventoryColor.query.filter_by(name=name.strip()).first()
        if existing:
            raise ValueError(f"Farbe mit Namen '{name}' existiert bereits")
        
        # Prüfe ob Hex-Wert bereits existiert
        existing_hex = InventoryColor.query.filter_by(color_hex=color_hex.strip().upper()).first()
        if existing_hex:
            raise ValueError(f"Farbe mit Hex-Wert '{color_hex}' existiert bereits")
        
        color = InventoryColor(
            name=name.strip(),
            color_hex=color_hex.strip().upper(),
            description=description,
            sort_order=sort_order,
            active=True,
            created_by=created_by,
        )
        
        db.session.add(color)
        db.session.commit()
        
        return color
    
    @staticmethod
    def get_color(color_id: int) -> Optional[InventoryColor]:
        """Holt eine Farbe nach ID."""
        return InventoryColor.query.get(color_id)
    
    @staticmethod
    def get_all_colors(include_inactive: bool = False) -> List[InventoryColor]:
        """Holt alle Farben."""
        query = InventoryColor.query
        if not include_inactive:
            query = query.filter_by(active=True)
        return query.order_by(
            InventoryColor.sort_order,
            InventoryColor.name,
        ).all()
    
    @staticmethod
    def update_color(
        color_id: int,
        name: Optional[str] = None,
        color_hex: Optional[str] = None,
        description: Optional[str] = None,
        sort_order: Optional[int] = None,
        active: Optional[bool] = None,
        updated_by: Optional[int] = None,
    ) -> InventoryColor:
        """
        Aktualisiert eine Farbe.
        
        Args:
            color_id: ID der Farbe
            name: Neuer Name
            color_hex: Neuer Hex-Wert
            description: Neue Beschreibung
            sort_order: Neue Sortierordnung
            active: Neuer Aktiv-Status
            updated_by: Benutzer-ID der die Änderung durchführt
            
        Returns:
            Die aktualisierte Farbe
            
        Raises:
            ValueError: Wenn Farbe nicht existiert
        """
        color = InventoryColor.query.get(color_id)
        if not color:
            raise ValueError(f"Farbe mit ID {color_id} existiert nicht")
        
        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("Farbname ist erforderlich")
            # Prüfe ob Name bereits existiert (außer bei sich selbst)
            existing = InventoryColor.query.filter_by(name=name).first()
            if existing and existing.id != color_id:
                raise ValueError(f"Farbe mit Namen '{name}' existiert bereits")
            color.name = name
        
        if color_hex is not None:
            color_hex = color_hex.strip().upper()
            if not color_hex:
                raise ValueError("Hex-Farbwert ist erforderlich")
            # Prüfe ob Hex-Wert bereits existiert (außer bei sich selbst)
            existing_hex = InventoryColor.query.filter_by(color_hex=color_hex).first()
            if existing_hex and existing_hex.id != color_id:
                raise ValueError(f"Farbe mit Hex-Wert '{color_hex}' existiert bereits")
            color.color_hex = color_hex
        
        if description is not None:
            color.description = description
        if sort_order is not None:
            color.sort_order = sort_order
        if active is not None:
            color.active = active
        
        color.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return color
    
    @staticmethod
    def deactivate_color(color_id: int, deleted_by: Optional[int] = None) -> InventoryColor:
        """
        Deaktiviert eine Farbe.
        
        Args:
            color_id: ID der Farbe
            deleted_by: Benutzer-ID der die Deaktivierung durchführt
            
        Returns:
            Die deaktivierte Farbe
            
        Raises:
            ValueError: Wenn Farbe nicht existiert
        """
        color = InventoryColor.query.get(color_id)
        if not color:
            raise ValueError(f"Farbe mit ID {color_id} existiert nicht")
        
        color.active = False
        color.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return color
    
    @staticmethod
    def delete_color(color_id: int, deleted_by: Optional[int] = None) -> None:
        """
        Löscht eine Farbe physisch.
        
        ACHTUNG: Dies entfernt die Farbe dauerhaft. Farbzuordnungen von Instanzen
        werden auf NULL gesetzt.
        
        Args:
            color_id: ID der Farbe
            deleted_by: Benutzer-ID der die Löschung durchführt
            
        Raises:
            ValueError: Wenn Farbe nicht existiert
        """
        color = InventoryColor.query.get(color_id)
        if not color:
            raise ValueError(f"Farbe mit ID {color_id} existiert nicht")
        
        # Setze Farbzuordnungen auf NULL
        ProductInstance.query.filter_by(color_id=color_id).update({'color_id': None})
        
        db.session.delete(color)
        db.session.commit()
    
    @staticmethod
    def get_color_by_hex(color_hex: str) -> Optional[InventoryColor]:
        """Holt eine Farbe nach Hex-Wert."""
        return InventoryColor.query.filter_by(
            color_hex=color_hex.strip().upper(),
            active=True,
        ).first()
    
    @staticmethod
    def get_color_by_name(name: str) -> Optional[InventoryColor]:
        """Holt eine Farbe nach Name."""
        return InventoryColor.query.filter_by(
            name=name.strip(),
            active=True,
        ).first()
