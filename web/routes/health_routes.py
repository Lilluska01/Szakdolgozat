from flask import Blueprint,jsonify
from services.health_service import SystemHealthService
from web.auth import require_auth

health_bp=Blueprint('health_details',__name__)
service=SystemHealthService()

@health_bp.get('/details')
@require_auth('admin')
def details():
    report=service.details()
    return jsonify(report),200 if report['status']=='ok' else 503
