from flask import Blueprint, jsonify, request
from services.access_service import AccessService
from services.serialization import to_json_value
from web.auth import require_auth

access_bp = Blueprint('access', __name__)
service = AccessService()

@access_bp.get('/logs')
@require_auth('admin')
def logs():
    limit = request.args.get('limit', default=50, type=int)
    return jsonify(to_json_value(service.get_last_logs(limit)))

@access_bp.get('/inside')
@require_auth('admin')
def inside():
    return jsonify(to_json_value(service.get_currently_inside()))

@access_bp.get('/summary')
@require_auth('admin')
def summary():
    return jsonify(to_json_value(service.get_summary()))

@access_bp.post('/scan')
@require_auth('admin')
def scan():
    data = request.get_json(silent=True) or {}
    result = service.record_scan(data.get('card_id'), source='api')
    status_code = 200 if result['status'] in {'ENTRY', 'EXIT', 'COOLDOWN'} else 403
    return jsonify(to_json_value(result)), status_code
@access_bp.post('/users/<int:user_id>/force-exit')
@require_auth('admin')
def force_exit(user_id):
    data=request.get_json(silent=True) or {}
    try:
        return jsonify(to_json_value(service.force_exit(user_id,g.identity['user_id'],data.get('reason'))))
    except ValueError as exc:
        return jsonify({'error':'invalid_operation','message':str(exc)}),400


@access_bp.get('/presence-report')
@require_auth('admin')
def presence_report():
    from datetime import date
    requested=request.args.get('date') or date.today().isoformat()
    try:
        return jsonify(to_json_value(service.daily_presence_report(requested)))
    except ValueError as exc:
        return jsonify({'error':'validation_error','message':str(exc)}),400
