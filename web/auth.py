from functools import wraps
from flask import request, jsonify, g
from services.auth_service import AuthService

auth_service=AuthService()

def require_auth(*roles):
    def decorate(view):
        @wraps(view)
        def wrapped(*args,**kwargs):
            identity=auth_service.get_token_user(request.headers.get('Authorization',''))
            if not identity:
                return jsonify({'error':'unauthorized','message':'Érvényes, be nem vont Bearer token szükséges.'}),401
            if roles and identity.get('role') not in roles:
                return jsonify({'error':'forbidden','message':'Nincs jogosultság ehhez a művelethez.'}),403
            g.identity=identity
            return view(*args,**kwargs)
        return wrapped
    return decorate
