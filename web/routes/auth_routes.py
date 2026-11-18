from flask import Blueprint, jsonify, request, g
from services.auth_service import AuthService
from web.auth import require_auth

auth_bp=Blueprint('auth',__name__)
service=AuthService()

@auth_bp.post('/login')
def login():
    data=request.get_json(silent=True) or {}
    token=service.login(data.get('email'),data.get('password'))
    if not token:
        return jsonify({'error':'invalid_credentials','message':'Hibás e-mail vagy jelszó.'}),401
    return jsonify({'token':token,'token_type':'Bearer'})

@auth_bp.get('/me')
@require_auth()
def me():
    return jsonify({key:g.identity.get(key) for key in ('user_id','name','email','role')})

@auth_bp.post('/logout')
@require_auth()
def logout():
    service.revoke_token(request.headers.get('Authorization',''))
    return jsonify({'status':'logged_out'})

@auth_bp.post('/change-password')
@require_auth()
def change_password():
    data=request.get_json(silent=True) or {}
    try:
        service.change_password(g.identity['user_id'],data.get('current_password'),data.get('new_password'))
        return jsonify({'status':'password_changed','message':'Jelentkezz be újra az új jelszóval.'})
    except ValueError as exc:
        return jsonify({'error':'password_change_failed','message':str(exc)}),400
