"""
API-Endpunkte für Produktinstanzen (individuelle Exemplare).

Diese Blueprints bieten RESTful Endpunkte für die Verwaltung von
Produktinstanzen, Farben und Status-Historie.
"""

from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required

from app import db
from app.models.inventory import Product, ProductInstance, InventoryColor, ProductInstanceStatusHistory
from app.services.inventory import InstanceService, ColorService, VALID_INSTANCE_STATUSES

from .common import api_error, api_ok

instances_bp = Blueprint("inventory_vnext_instances", __name__)


# ============================================================================
# Produktinstanzen (ProductInstance)
# ============================================================================

@instances_bp.route("/products/<int:product_id>/instances", methods=["GET"])
@login_required
def get_product_instances(product_id):
    """Holt alle Instanzen eines Produkts."""
    product = Product.query.get_or_404(product_id)
    
    # Filter
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    status = request.args.get('status', None)
    search = request.args.get('search', '').strip()
    
    # Pagination
    offset = max(0, request.args.get('offset', 0, type=int) or 0)
    limit_raw = request.args.get('limit', default=100, type=int)
    limit = min(max(1, limit_raw or 100), 500)
    
    query = ProductInstance.query.filter_by(product_id=product_id)
    
    if not include_inactive:
        query = query.filter_by(active=True)
    
    if status and status in VALID_INSTANCE_STATUSES:
        query = query.filter_by(status=status)
    
    if search:
        query = query.filter(
            db.or_(
                ProductInstance.inventory_number.ilike(f'%{search}%'),
                ProductInstance.serial_number.ilike(f'%{search}%'),
                ProductInstance.dguv_id.ilike(f'%{search}%'),
                ProductInstance.location.ilike(f'%{search}%'),
            )
        )
    
    # Sortierung
    query = query.order_by(
        ProductInstance.status,
        ProductInstance.inventory_number,
        ProductInstance.serial_number,
        ProductInstance.id,
    )
    
    total = query.count()
    instances = query.offset(offset).limit(limit).all()
    
    return api_ok({
        "product_id": product_id,
        "instances": [serialize_instance(i) for i in instances],
        "total": total,
        "offset": offset,
        "limit": limit,
    })


@instances_bp.route("/products/<int:product_id>/instances", methods=["POST"])
@login_required
def create_product_instance(product_id):
    """Erstellt eine neue Produktinstanz."""
    product = Product.query.get_or_404(product_id)
    data = request.get_json() or {}
    
    # Validierung
    if not data.get('inventory_number') and not data.get('serial_number'):
        return api_error(
            "identification_required",
            "Mindestens Inventarnummer oder Seriennummer ist erforderlich.",
            400
        )
    
    try:
        instance = InstanceService.create_instance(
            product_id=product_id,
            inventory_number=data.get('inventory_number'),
            serial_number=data.get('serial_number'),
            status=data.get('status', 'available'),
            dguv_enabled=data.get('dguv_enabled', False),
            dguv_id=data.get('dguv_id'),
            color_id=data.get('color_id'),
            color_override=data.get('color_override'),
            location=data.get('location'),
            assigned_user_id=data.get('assigned_user_id'),
            notes=data.get('notes'),
            created_by=current_user.id,
        )
        db.session.commit()
        
        return api_ok({
            "message": "Instanz erfolgreich erstellt",
            "instance": serialize_instance(instance),
        }, 201)
    except ValueError as e:
        db.session.rollback()
        return api_error("validation_error", str(e), 400)


@instances_bp.route("/instances/<int:instance_id>", methods=["GET"])
@login_required
def get_instance(instance_id):
    """Holt eine spezifische Produktinstanz."""
    instance = ProductInstance.query.get_or_404(instance_id)
    
    return api_ok({
        "instance": serialize_instance(instance, include_history=True),
    })


@instances_bp.route("/instances/<int:instance_id>", methods=["PUT", "PATCH"])
@login_required
def update_instance(instance_id):
    """Aktualisiert eine Produktinstanz."""
    instance = ProductInstance.query.get_or_404(instance_id)
    data = request.get_json() or {}
    
    try:
        updated_instance = InstanceService.update_instance(
            instance_id=instance_id,
            inventory_number=data.get('inventory_number'),
            serial_number=data.get('serial_number'),
            status=data.get('status'),
            dguv_enabled=data.get('dguv_enabled'),
            dguv_id=data.get('dguv_id'),
            color_id=data.get('color_id'),
            color_override=data.get('color_override'),
            location=data.get('location'),
            assigned_user_id=data.get('assigned_user_id'),
            notes=data.get('notes'),
            active=data.get('active'),
            updated_by=current_user.id,
        )
        db.session.commit()
        
        return api_ok({
            "message": "Instanz erfolgreich aktualisiert",
            "instance": serialize_instance(updated_instance),
        })
    except ValueError as e:
        db.session.rollback()
        return api_error("validation_error", str(e), 400)


@instances_bp.route("/instances/<int:instance_id>/status", methods=["POST"])
@login_required
def change_instance_status(instance_id):
    """Ändert den Status einer Produktinstanz."""
    instance = ProductInstance.query.get_or_404(instance_id)
    data = request.get_json() or {}
    
    new_status = data.get('status')
    reason = data.get('reason', '').strip() or None
    
    if not new_status:
        return api_error("status_required", "Neuer Status ist erforderlich.", 400)
    
    if new_status not in VALID_INSTANCE_STATUSES:
        return api_error(
            "invalid_status",
            f"Ungültiger Status: {new_status}. Erlaubt: {', '.join(VALID_INSTANCE_STATUSES)}",
            400
        )
    
    try:
        updated_instance = InstanceService.change_status(
            instance_id=instance_id,
            new_status=new_status,
            reason=reason,
            changed_by=current_user.id,
        )
        db.session.commit()
        
        return api_ok({
            "message": "Status erfolgreich geändert",
            "instance": serialize_instance(updated_instance),
        })
    except ValueError as e:
        db.session.rollback()
        return api_error("error", str(e), 400)


@instances_bp.route("/instances/<int:instance_id>/deactivate", methods=["POST"])
@login_required
def deactivate_instance(instance_id):
    """Deaktiviert eine Produktinstanz (Soft Delete)."""
    instance = ProductInstance.query.get_or_404(instance_id)
    data = request.get_json() or {}
    
    reason = data.get('reason', '').strip() or None
    
    try:
        deactivated_instance = InstanceService.deactivate_instance(
            instance_id=instance_id,
            reason=reason,
            deleted_by=current_user.id,
        )
        db.session.commit()
        
        return api_ok({
            "message": "Instanz erfolgreich deaktiviert",
            "instance": serialize_instance(deactivated_instance),
        })
    except ValueError as e:
        db.session.rollback()
        return api_error("error", str(e), 400)


@instances_bp.route("/instances/<int:instance_id>", methods=["DELETE"])
@login_required
def delete_instance(instance_id):
    """Löscht eine Produktinstanz physisch."""
    instance = ProductInstance.query.get_or_404(instance_id)
    
    try:
        InstanceService.delete_instance(
            instance_id=instance_id,
            deleted_by=current_user.id,
        )
        db.session.commit()
        
        return api_ok({
            "message": "Instanz erfolgreich gelöscht",
        })
    except ValueError as e:
        db.session.rollback()
        return api_error("error", str(e), 400)


@instances_bp.route("/instances/<int:instance_id>/history", methods=["GET"])
@login_required
def get_instance_history(instance_id):
    """Holt die Status-Historie einer Produktinstanz."""
    instance = ProductInstance.query.get_or_404(instance_id)
    
    history = InstanceService.get_status_history(instance_id)
    
    return api_ok({
        "instance_id": instance_id,
        "history": [serialize_history(h) for h in history],
    })


@instances_bp.route("/instances/search", methods=["GET"])
@login_required
def search_instances():
    """Durchsucht alle Produktinstanzen mit Filtern."""
    # Filter
    product_id = request.args.get('product_id', type=int)
    inventory_number = request.args.get('inventory_number', '').strip()
    serial_number = request.args.get('serial_number', '').strip()
    status = request.args.get('status', None)
    dguv_id = request.args.get('dguv_id', '').strip()
    color_id = request.args.get('color_id', type=int)
    location = request.args.get('location', '').strip()
    assigned_user_id = request.args.get('assigned_user_id', type=int)
    search_query = request.args.get('search', '').strip()
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    
    # Pagination
    offset = max(0, request.args.get('offset', 0, type=int) or 0)
    limit_raw = request.args.get('limit', default=50, type=int)
    limit = min(max(1, limit_raw or 50), 200)
    
    result = InstanceService.search_instances(
        product_id=product_id,
        inventory_number=inventory_number,
        serial_number=serial_number,
        status=status,
        dguv_id=dguv_id,
        color_id=color_id,
        location=location,
        assigned_user_id=assigned_user_id,
        search_query=search_query,
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )
    
    return api_ok({
        "instances": [serialize_instance(i) for i in result['items']],
        "total": result['total'],
        "offset": result['offset'],
        "limit": result['limit'],
    })


# ============================================================================
# Farben (InventoryColor)
# ============================================================================

@instances_bp.route("/colors", methods=["GET"])
@login_required
def get_colors():
    """Holt alle Farben."""
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    
    colors = ColorService.get_all_colors(include_inactive=include_inactive)
    
    return api_ok({
        "colors": [serialize_color(c) for c in colors],
    })


@instances_bp.route("/colors", methods=["POST"])
@login_required
def create_color():
    """Erstellt eine neue Farbe."""
    data = request.get_json() or {}
    
    try:
        color = ColorService.create_color(
            name=data.get('name'),
            color_hex=data.get('color_hex'),
            description=data.get('description'),
            sort_order=data.get('sort_order', 0),
            created_by=current_user.id,
        )
        db.session.commit()
        
        return api_ok({
            "message": "Farbe erfolgreich erstellt",
            "color": serialize_color(color),
        }, 201)
    except ValueError as e:
        db.session.rollback()
        return api_error("validation_error", str(e), 400)


@instances_bp.route("/colors/<int:color_id>", methods=["GET"])
@login_required
def get_color(color_id):
    """Holt eine spezifische Farbe."""
    color = InventoryColor.query.get_or_404(color_id)
    
    return api_ok({
        "color": serialize_color(color),
    })


@instances_bp.route("/colors/<int:color_id>", methods=["PUT", "PATCH"])
@login_required
def update_color(color_id):
    """Aktualisiert eine Farbe."""
    color = InventoryColor.query.get_or_404(color_id)
    data = request.get_json() or {}
    
    try:
        updated_color = ColorService.update_color(
            color_id=color_id,
            name=data.get('name'),
            color_hex=data.get('color_hex'),
            description=data.get('description'),
            sort_order=data.get('sort_order'),
            active=data.get('active'),
            updated_by=current_user.id,
        )
        db.session.commit()
        
        return api_ok({
            "message": "Farbe erfolgreich aktualisiert",
            "color": serialize_color(updated_color),
        })
    except ValueError as e:
        db.session.rollback()
        return api_error("validation_error", str(e), 400)


@instances_bp.route("/colors/<int:color_id>/deactivate", methods=["POST"])
@login_required
def deactivate_color(color_id):
    """Deaktiviert eine Farbe."""
    color = InventoryColor.query.get_or_404(color_id)
    
    try:
        deactivated_color = ColorService.deactivate_color(
            color_id=color_id,
            deleted_by=current_user.id,
        )
        db.session.commit()
        
        return api_ok({
            "message": "Farbe erfolgreich deaktiviert",
            "color": serialize_color(deactivated_color),
        })
    except ValueError as e:
        db.session.rollback()
        return api_error("error", str(e), 400)


@instances_bp.route("/colors/<int:color_id>", methods=["DELETE"])
@login_required
def delete_color(color_id):
    """Löscht eine Farbe."""
    color = InventoryColor.query.get_or_404(color_id)
    
    try:
        ColorService.delete_color(
            color_id=color_id,
            deleted_by=current_user.id,
        )
        db.session.commit()
        
        return api_ok({
            "message": "Farbe erfolgreich gelöscht",
        })
    except ValueError as e:
        db.session.rollback()
        return api_error("error", str(e), 400)


# ============================================================================
# Hilfsfunktionen für Serialisierung
# ============================================================================

def serialize_instance(instance: ProductInstance, include_history: bool = False) -> dict:
    """Serialisiert eine Produktinstanz für die API."""
    data = {
        "id": instance.id,
        "product_id": instance.product_id,
        "inventory_number": instance.inventory_number,
        "serial_number": instance.serial_number,
        "status": instance.status,
        "dguv_enabled": instance.dguv_enabled,
        "dguv_id": instance.dguv_id,
        "color_id": instance.color_id,
        "color_override": instance.color_override,
        "effective_color": instance.effective_color,
        "location": instance.location,
        "assigned_user_id": instance.assigned_user_id,
        "notes": instance.notes,
        "active": instance.active,
        "display_identifier": instance.display_identifier,
        "created_at": instance.created_at.isoformat() if instance.created_at else None,
        "updated_at": instance.updated_at.isoformat() if instance.updated_at else None,
    }
    
    if include_history:
        history = InstanceService.get_status_history(instance.id, limit=10)
        data["history"] = [serialize_history(h) for h in history]
    
    return data


def serialize_color(color: InventoryColor) -> dict:
    """Serialisiert eine Farbe für die API."""
    return {
        "id": color.id,
        "name": color.name,
        "color_hex": color.color_hex,
        "description": color.description,
        "sort_order": color.sort_order,
        "active": color.active,
        "created_at": color.created_at.isoformat() if color.created_at else None,
        "updated_at": color.updated_at.isoformat() if color.updated_at else None,
    }


def serialize_history(history: ProductInstanceStatusHistory) -> dict:
    """Serialisiert einen Status-Historie-Eintrag für die API."""
    return {
        "id": history.id,
        "instance_id": history.instance_id,
        "old_status": history.old_status,
        "new_status": history.new_status,
        "reason": history.reason,
        "note": history.note,
        "changed_by": history.changed_by,
        "changed_at": history.changed_at.isoformat() if history.changed_at else None,
    }
