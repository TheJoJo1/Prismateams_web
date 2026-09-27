"""
Label-Template Modell für den Etiketten-Designer.

Dieses Modell ermöglicht die Erstellung und Verwaltung von
benutzerdefinierten Etiketten-Vorlagen mit dynamischen Elementen.
"""

from datetime import datetime
from app import db


# Gültige Element-Typen für Labels
LABEL_ELEMENT_TYPES = {
    'text',           # Statischer Text
    'product_name',   # Produktname
    'product_category',  # Produktkategorie
    'product_serial',    # Produktseriennummer
    'instance_inventory_number',  # Inventarnummer der Instanz
    'instance_serial_number',     # Seriennummer der Instanz
    'instance_dguv_id',           # DGUV-ID der Instanz
    'instance_status',            # Status der Instanz
    'instance_color',             # Farbe der Instanz
    'qr_code',        # QR-Code
    'barcode',        # Barcode
    'date',           # Aktuelles Datum
    'custom_field',   # Benutzerdefiniertes Feld
}


class LabelTemplate(db.Model):
    """
    Vorlage für Etiketten.
    
    Eine LabelTemplate definiert das Layout und die Elemente eines Etiketts.
    Sie kann für verschiedene Produkte und Instanzen wiederverwendet werden.
    """
    __tablename__ = 'label_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True, index=True)
    description = db.Column(db.Text, nullable=True)
    
    # Abmessungen
    width_mm = db.Column(db.Float, default=50.0, nullable=False)  # Breite in Millimetern
    height_mm = db.Column(db.Float, default=30.0, nullable=False)  # Höhe in Millimetern
    unit = db.Column(db.String(10), default='mm', nullable=False)  # Einheit: mm, cm, inch
    
    # Seitenränder
    margin_top_mm = db.Column(db.Float, default=2.0, nullable=False)
    margin_right_mm = db.Column(db.Float, default=2.0, nullable=False)
    margin_bottom_mm = db.Column(db.Float, default=2.0, nullable=False)
    margin_left_mm = db.Column(db.Float, default=2.0, nullable=False)
    
    # Hintergrund
    background_color = db.Column(db.String(7), nullable=True)  # Hex-Farbe
    background_image = db.Column(db.String(500), nullable=True)  # Pfad zu Hintergrundbild
    
    # Metadaten
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by])
    elements = db.relationship('LabelTemplateElement', back_populates='template', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<LabelTemplate {self.name} ({self.width_mm}x{self.height_mm}{self.unit})>'
    
    @property
    def display_name(self):
        """Gibt den Anzeigenamen zurück."""
        return self.name
    
    @property
    def element_count(self):
        """Anzahl der Elemente in der Vorlage."""
        return len(self.elements)


class LabelTemplateElement(db.Model):
    """
    Einzelnes Element in einer Label-Vorlage.
    
    Jedes Element hat eine Position, Größe und einen Inhaltstyp.
    Der Inhalt kann statisch sein oder dynamisch aus Produkt-/Instanz-Daten generiert werden.
    """
    __tablename__ = 'label_template_elements'
    
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('label_templates.id'), nullable=False, index=True)
    
    # Position und Größe
    x_mm = db.Column(db.Float, default=0.0, nullable=False)  # X-Position in Millimetern
    y_mm = db.Column(db.Float, default=0.0, nullable=False)  # Y-Position in Millimetern
    width_mm = db.Column(db.Float, default=20.0, nullable=False)  # Breite in Millimetern
    height_mm = db.Column(db.Float, default=10.0, nullable=False)  # Höhe in Millimetern
    
    # Element-Typ
    element_type = db.Column(db.String(50), default='text', nullable=False, index=True)
    
    # Inhalt
    content = db.Column(db.Text, nullable=True)  # Statischer Inhalt oder Template-String
    
    # Formatierung
    font_family = db.Column(db.String(100), default='Arial', nullable=False)
    font_size_pt = db.Column(db.Float, default=10.0, nullable=False)  # Schriftgröße in Punkt
    font_weight = db.Column(db.String(20), default='normal', nullable=False)  # normal, bold, light
    font_style = db.Column(db.String(20), default='normal', nullable=False)  # normal, italic
    text_color = db.Column(db.String(7), default='#000000', nullable=False)  # Textfarbe
    text_align = db.Column(db.String(20), default='left', nullable=False)  # left, center, right
    
    # Rahmen
    border_width_mm = db.Column(db.Float, default=0.0, nullable=False)
    border_color = db.Column(db.String(7), nullable=True)
    border_radius_mm = db.Column(db.Float, default=0.0, nullable=False)
    
    # Hintergrund
    background_color = db.Column(db.String(7), nullable=True)
    
    # Rotation
    rotation_degrees = db.Column(db.Float, default=0.0, nullable=False)  # Rotation in Grad
    
    # Sortierordnung (Z-Index)
    z_index = db.Column(db.Integer, default=0, nullable=False)
    
    # Zusätzliche Konfiguration (JSON)
    configuration = db.Column(db.Text, nullable=True)  # JSON für typ-spezifische Einstellungen
    
    # Metadaten
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    template = db.relationship('LabelTemplate', back_populates='elements')
    
    def __repr__(self):
        return f'<LabelTemplateElement {self.element_type} at ({self.x_mm},{self.y_mm}) in {self.template_id}>'
    
    @property
    def display_content(self):
        """Gibt eine lesbare Darstellung des Inhalts zurück."""
        if not self.content:
            return f'[{self.element_type}]'
        if len(self.content) > 50:
            return f'{self.content[:50]}...'
        return self.content
    
    def get_configuration(self):
        """Gibt die Konfiguration als Dictionary zurück."""
        import json
        if self.configuration:
            try:
                return json.loads(self.configuration)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    def set_configuration(self, config_dict):
        """Setzt die Konfiguration aus einem Dictionary."""
        import json
        if config_dict:
            self.configuration = json.dumps(config_dict)
        else:
            self.configuration = None


class LabelPrintJob(db.Model):
    """
    Druckauftrag für Etiketten.
    
    Speichert Informationen über Druckaufträge, um sie später nachvollziehen zu können.
    """
    __tablename__ = 'label_print_jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    job_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # Druckeinstellungen
    template_id = db.Column(db.Integer, db.ForeignKey('label_templates.id'), nullable=True, index=True)
    label_count = db.Column(db.Integer, default=1, nullable=False)
    copies_per_label = db.Column(db.Integer, default=1, nullable=False)
    
    # Datenquelle
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, index=True)
    instance_ids = db.Column(db.Text, nullable=True)  # JSON-Liste der Instanz-IDs
    
    # Status
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)  # pending, printing, completed, failed
    error_message = db.Column(db.Text, nullable=True)
    
    # Metadaten
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by])
    template = db.relationship('LabelTemplate')
    product = db.relationship('Product', foreign_keys=[product_id])
    
    def __repr__(self):
        return f'<LabelPrintJob {self.job_number} ({self.status})>'
    
    @property
    def total_labels(self):
        """Gesamtanzahl der zu druckenden Etiketten."""
        return self.label_count * self.copies_per_label
    
    def get_instance_ids(self):
        """Gibt die Liste der Instanz-IDs zurück."""
        import json
        if self.instance_ids:
            try:
                return json.loads(self.instance_ids)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    def set_instance_ids(self, instance_id_list):
        """Setzt die Liste der Instanz-IDs."""
        import json
        if instance_id_list:
            self.instance_ids = json.dumps(instance_id_list)
        else:
            self.instance_ids = None
