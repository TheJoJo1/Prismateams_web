"""
API-Endpunkte für Label-Vorlagen und Druck.
"""

from flask import Blueprint, request, jsonify, send_file
from flask_login import current_user, login_required

from app import db
from app.models.label import LabelTemplate, LabelTemplateElement, LabelPrintJob, LABEL_ELEMENT_TYPES
from app.services.label_service import LabelService

from .common import api_error, api_ok

labels_bp = Blueprint("inventory_vnext_labels", __name__)


# ============================================================================
# Label-Vorlagen (LabelTemplate)
# ============================================================================

@labels_bp.route("/label-templates", methods=["GET"])
@login_required
def get_label_templates():
    """Holt alle Label-Vorlagen."""
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    
    templates = LabelService.get_all_templates(include_inactive=include_inactive)
    
    return api_ok({
        "templates": [serialize_template(t) for t in templates],
    })


@labels_bp.route("/label-templates", methods=["POST"])
@login_required
def create_label_template():
    """Erstellt eine neue Label-Vorlage."""
    data = request.get_json() or {}
    
    try:
        template = LabelService.create_template(
            name=data.get('name'),
            width_mm=data.get('width_mm', 50.0),
            height_mm=data.get('height_mm', 30.0),
            unit=data.get('unit', 'mm'),
            description=data.get('description'),
            background_color=data.get('background_color'),
            margin_top_mm=data.get('margin_top_mm', 2.0),
            margin_right_mm=data.get('margin_right_mm', 2.0),
            margin_bottom_mm=data.get('margin_bottom_mm', 2.0),
            margin_left_mm=data.get('margin_left_mm', 2.0),
            created_by=current_user.id,
        )
        db.session.commit()
        
        return api_ok({
            "message": "Label-Vorlage erfolgreich erstellt",
            "template": serialize_template(template),
        }, 201)
    except ValueError as e:
        db.session.rollback()
        return api_error("validation_error", str(e), 400)


@labels_bp.route("/label-templates/<int:template_id>", methods=["GET"])
@login_required
def get_label_template(template_id):
    """Holt eine spezifische Label-Vorlage."""
    template = LabelTemplate.query.get_or_404(template_id)
    
    return api_ok({
        "template": serialize_template(template, include_elements=True),
    })


@labels_bp.route("/label-templates/<int:template_id>", methods=["PUT", "PATCH"])
@login_required
def update_label_template(template_id):
    """Aktualisiert eine Label-Vorlage."""
    template = LabelTemplate.query.get_or_404(template_id)
    data = request.get_json() or {}
    
    try:
        updated_template = LabelService.update_template(
            template_id=template_id,
            name=data.get('name'),
            width_mm=data.get('width_mm'),
            height_mm=data.get('height_mm'),
            unit=data.get('unit'),
            description=data.get('description'),
            background_color=data.get('background_color'),
            margin_top_mm=data.get('margin_top_mm'),
            margin_right_mm=data.get('margin_right_mm'),
            margin_bottom_mm=data.get('margin_bottom_mm'),
            margin_left_mm=data.get('margin_left_mm'),
            active=data.get('active'),
            updated_by=current_user.id,
        )
        db.session.commit()
        
        return api_ok({
            "message": "Label-Vorlage erfolgreich aktualisiert",
            "template": serialize_template(updated_template),
        })
    except ValueError as e:
        db.session.rollback()
        return api_error("validation_error", str(e), 400)


@labels_bp.route("/label-templates/<int:template_id>", methods=["DELETE"])
@login_required
def delete_label_template(template_id):
    """Löscht eine Label-Vorlage."""
    template = LabelTemplate.query.get_or_404(template_id)
    
    try:
        LabelService.delete_template(
            template_id=template_id,
            deleted_by=current_user.id,
        )
        db.session.commit()
        
        return api_ok({
            "message": "Label-Vorlage erfolgreich gelöscht",
        })
    except ValueError as e:
        db.session.rollback()
        return api_error("error", str(e), 400)


# ============================================================================
# Label-Elemente (LabelTemplateElement)
# ============================================================================

@labels_bp.route("/label-templates/<int:template_id>/elements", methods=["POST"])
@login_required
def create_label_element(template_id):
    """Fügt ein Element zu einer Label-Vorlage hinzu."""
    template = LabelTemplate.query.get_or_404(template_id)
    data = request.get_json() or {}
    
    try:
        element = LabelService.add_element(
            template_id=template_id,
            element_type=data.get('element_type', 'text'),
            x_mm=data.get('x_mm', 0.0),
            y_mm=data.get('y_mm', 0.0),
            width_mm=data.get('width_mm', 20.0),
            height_mm=data.get('height_mm', 10.0),
            content=data.get('content'),
            font_family=data.get('font_family', 'Arial'),
            font_size_pt=data.get('font_size_pt', 10.0),
            font_weight=data.get('font_weight', 'normal'),
            font_style=data.get('font_style', 'normal'),
            text_color=data.get('text_color', '#000000'),
            text_align=data.get('text_align', 'left'),
            border_width_mm=data.get('border_width_mm', 0.0),
            border_color=data.get('border_color'),
            border_radius_mm=data.get('border_radius_mm', 0.0),
            background_color=data.get('background_color'),
            rotation_degrees=data.get('rotation_degrees', 0.0),
            z_index=data.get('z_index', 0),
            configuration=data.get('configuration'),
        )
        db.session.commit()
        
        return api_ok({
            "message": "Label-Element erfolgreich hinzugefügt",
            "element": serialize_element(element),
        }, 201)
    except ValueError as e:
        db.session.rollback()
        return api_error("validation_error", str(e), 400)


@labels_bp.route("/label-elements/<int:element_id>", methods=["PUT", "PATCH"])
@login_required
def update_label_element(element_id):
    """Aktualisiert ein Label-Element."""
    element = LabelTemplateElement.query.get_or_404(element_id)
    data = request.get_json() or {}
    
    try:
        updated_element = LabelService.update_element(
            element_id=element_id,
            element_type=data.get('element_type'),
            x_mm=data.get('x_mm'),
            y_mm=data.get('y_mm'),
            width_mm=data.get('width_mm'),
            height_mm=data.get('height_mm'),
            content=data.get('content'),
            font_family=data.get('font_family'),
            font_size_pt=data.get('font_size_pt'),
            font_weight=data.get('font_weight'),
            font_style=data.get('font_style'),
            text_color=data.get('text_color'),
            text_align=data.get('text_align'),
            border_width_mm=data.get('border_width_mm'),
            border_color=data.get('border_color'),
            border_radius_mm=data.get('border_radius_mm'),
            background_color=data.get('background_color'),
            rotation_degrees=data.get('rotation_degrees'),
            z_index=data.get('z_index'),
            configuration=data.get('configuration'),
        )
        db.session.commit()
        
        return api_ok({
            "message": "Label-Element erfolgreich aktualisiert",
            "element": serialize_element(updated_element),
        })
    except ValueError as e:
        db.session.rollback()
        return api_error("validation_error", str(e), 400)


@labels_bp.route("/label-elements/<int:element_id>", methods=["DELETE"])
@login_required
def delete_label_element(element_id):
    """Löscht ein Label-Element."""
    element = LabelTemplateElement.query.get_or_404(element_id)
    
    try:
        LabelService.delete_element(element_id=element_id)
        db.session.commit()
        
        return api_ok({
            "message": "Label-Element erfolgreich gelöscht",
        })
    except ValueError as e:
        db.session.rollback()
        return api_error("error", str(e), 400)


# ============================================================================
# Druckaufträge (LabelPrintJob)
# ============================================================================

@labels_bp.route("/label-print-jobs", methods=["GET"])
@login_required
def get_label_print_jobs():
    """Holt alle Druckaufträge."""
    status = request.args.get('status', None)
    limit = max(1, min(100, request.args.get('limit', 50, type=int) or 50))
    offset = max(0, request.args.get('offset', 0, type=int) or 0)
    
    jobs = LabelService.get_print_jobs(
        status=status,
        created_by=current_user.id,
        limit=limit,
        offset=offset,
    )
    
    return api_ok({
        "jobs": [serialize_print_job(j) for j in jobs],
    })


@labels_bp.route("/label-print-jobs", methods=["POST"])
@login_required
def create_label_print_job():
    """Erstellt einen neuen Druckauftrag."""
    data = request.get_json() or {}
    
    try:
        job = LabelService.create_print_job(
            template_id=data.get('template_id'),
            product_id=data.get('product_id'),
            instance_ids=data.get('instance_ids'),
            label_count=data.get('label_count', 1),
            copies_per_label=data.get('copies_per_label', 1),
            created_by=current_user.id,
        )
        db.session.commit()
        
        return api_ok({
            "message": "Druckauftrag erfolgreich erstellt",
            "job": serialize_print_job(job),
        }, 201)
    except ValueError as e:
        db.session.rollback()
        return api_error("validation_error", str(e), 400)


@labels_bp.route("/label-print-jobs/<int:job_id>", methods=["GET"])
@login_required
def get_label_print_job(job_id):
    """Holt einen spezifischen Druckauftrag."""
    job = LabelPrintJob.query.get_or_404(job_id)
    
    return api_ok({
        "job": serialize_print_job(job),
    })


@labels_bp.route("/label-print-jobs/<int:job_id>/status", methods=["POST"])
@login_required
def update_label_print_job_status(job_id):
    """Aktualisiert den Status eines Druckauftrags."""
    job = LabelPrintJob.query.get_or_404(job_id)
    data = request.get_json() or {}
    
    new_status = data.get('status')
    error_message = data.get('error_message')
    
    if not new_status:
        return api_error("status_required", "Status ist erforderlich", 400)
    
    try:
        updated_job = LabelService.update_print_job_status(
            job_id=job_id,
            status=new_status,
            error_message=error_message,
        )
        db.session.commit()
        
        return api_ok({
            "message": "Druckauftrag-Status erfolgreich aktualisiert",
            "job": serialize_print_job(updated_job),
        })
    except ValueError as e:
        db.session.rollback()
        return api_error("error", str(e), 400)


@labels_bp.route("/label-templates/<int:template_id>/render", methods=["POST"])
@login_required
def render_label_template(template_id):
    """Rendert eine Label-Vorlage mit Daten."""
    template = LabelTemplate.query.get_or_404(template_id)
    data = request.get_json() or {}
    
    product_id = data.get('product_id')
    instance_id = data.get('instance_id')
    
    product = None
    instance = None
    
    if product_id:
        from app.models.inventory import Product
        product = Product.query.get(product_id)
    
    if instance_id:
        from app.models.inventory import ProductInstance
        instance = ProductInstance.query.get(instance_id)
    
    try:
        rendered = LabelService.render_template(
            template=template,
            product=product,
            instance=instance,
            data=data.get('data'),
        )
        
        return api_ok({
            "rendered": rendered,
        })
    except Exception as e:
        return api_error("render_error", str(e), 500)


@labels_bp.route("/label-templates/<int:template_id>/preview", methods=["GET"])
@login_required
def preview_label_template(template_id):
    """Generiert eine Vorschau der Label-Vorlage als PDF."""
    template = LabelTemplate.query.get_or_404(template_id)
    
    product_id = request.args.get('product_id', type=int)
    instance_id = request.args.get('instance_id', type=int)
    
    product = None
    instance = None
    
    if product_id:
        from app.models.inventory import Product
        product = Product.query.get(product_id)
    
    if instance_id:
        from app.models.inventory import ProductInstance
        instance = ProductInstance.query.get(instance_id)
    
    try:
        pdf_bytes = LabelService.generate_label_pdf(
            template=template,
            product=product,
            instance=instance,
        )
        
        return send_file(
            pdf_bytes,
            mimetype='application/pdf',
            as_attachment=False,
            download_name=f'label_preview_{template_id}.pdf',
        )
    except Exception as e:
        return api_error("preview_error", str(e), 500)


@labels_bp.route("/label-templates/placeholders", methods=["GET"])
@login_required
def get_label_placeholders():
    """Holt die verfügbaren Platzhalter für Label-Vorlagen."""
    placeholders = LabelService.get_available_placeholders()
    
    return api_ok({
        "placeholders": placeholders,
    })


# ============================================================================
# Hilfsfunktionen für Serialisierung
# ============================================================================

def serialize_template(template: LabelTemplate, include_elements: bool = False) -> dict:
    """Serialisiert eine Label-Vorlage für die API."""
    data = {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "width_mm": template.width_mm,
        "height_mm": template.height_mm,
        "unit": template.unit,
        "background_color": template.background_color,
        "margin_top_mm": template.margin_top_mm,
        "margin_right_mm": template.margin_right_mm,
        "margin_bottom_mm": template.margin_bottom_mm,
        "margin_left_mm": template.margin_left_mm,
        "active": template.active,
        "element_count": template.element_count,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }
    
    if include_elements:
        data["elements"] = [serialize_element(e) for e in template.elements]
    
    return data


def serialize_element(element: LabelTemplateElement) -> dict:
    """Serialisiert ein Label-Element für die API."""
    return {
        "id": element.id,
        "template_id": element.template_id,
        "element_type": element.element_type,
        "x_mm": element.x_mm,
        "y_mm": element.y_mm,
        "width_mm": element.width_mm,
        "height_mm": element.height_mm,
        "content": element.content,
        "font_family": element.font_family,
        "font_size_pt": element.font_size_pt,
        "font_weight": element.font_weight,
        "font_style": element.font_style,
        "text_color": element.text_color,
        "text_align": element.text_align,
        "border_width_mm": element.border_width_mm,
        "border_color": element.border_color,
        "border_radius_mm": element.border_radius_mm,
        "background_color": element.background_color,
        "rotation_degrees": element.rotation_degrees,
        "z_index": element.z_index,
        "configuration": element.get_configuration(),
        "created_at": element.created_at.isoformat() if element.created_at else None,
        "updated_at": element.updated_at.isoformat() if element.updated_at else None,
    }


def serialize_print_job(job: LabelPrintJob) -> dict:
    """Serialisiert einen Druckauftrag für die API."""
    return {
        "id": job.id,
        "job_number": job.job_number,
        "template_id": job.template_id,
        "product_id": job.product_id,
        "instance_ids": job.get_instance_ids(),
        "label_count": job.label_count,
        "copies_per_label": job.copies_per_label,
        "total_labels": job.total_labels,
        "status": job.status,
        "error_message": job.error_message,
        "created_by": job.created_by,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
