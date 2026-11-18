from flask import Blueprint, jsonify, request, g
from services.student_import_service import StudentImportService, ImportValidationError
from services.serialization import to_json_value
from web.auth import require_auth

import_bp=Blueprint('student_import',__name__)
service=StudentImportService()

@import_bp.post('/preview')
@require_auth('admin')
def preview_import():
    uploaded=request.files.get('file')
    if uploaded is None:
        return jsonify({'error':'file_required'}),400
    try:
        data=uploaded.stream.read(1_500_001)
        result=service.preview(uploaded.filename,data)
        return jsonify(result)
    except ImportValidationError as exc:
        return jsonify({'error':'invalid_import','message':str(exc)}),400

@import_bp.post('/commit')
@require_auth('admin')
def commit_import():
    uploaded=request.files.get('file')
    if uploaded is None:
        return jsonify({'error':'file_required'}),400
    try:
        result=service.import_file(uploaded.filename,uploaded.stream.read(1_500_001),g.identity['user_id'])
        return jsonify(result),201 if result['status']=='imported' else 200
    except ImportValidationError as exc:
        payload=exc.args[0]
        if isinstance(payload,dict):
            return jsonify({'error':'invalid_import',**payload}),400
        return jsonify({'error':'invalid_import','message':str(exc)}),400

@import_bp.get('/history')
@require_auth('admin')
def import_history():
    return jsonify(to_json_value(service.history(
        limit=request.args.get('limit',50,type=int),
        offset=request.args.get('offset',0,type=int))))
