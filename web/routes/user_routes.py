from flask import Blueprint,request,jsonify,g
from services.user_service import UserService
from services.auth_service import AuthService
from services.audit_service import AuditService
from services.serialization import to_json_value
from web.auth import require_auth

user_bp=Blueprint('users',__name__)
service=UserService();audit=AuditService();auth_service=AuthService()

@user_bp.get('/')
@require_auth('admin','teacher')
def get_users():
    try:
        query=request.args.get('q')
        role=request.args.get('role','student')
        include_inactive=request.args.get('include_inactive','true').lower()!='false'
        limit=request.args.get('limit',100,type=int)
        offset=request.args.get('offset',0,type=int)
        if g.identity['role']=='teacher':
            if role!='student':
                return jsonify({'error':'forbidden','message':'Az oktatói felület csak a saját hallgatókat listázza.'}),403
            rows=service.list_students_for_teacher(g.identity['user_id'],search=query,limit=limit,offset=offset)
            total=len(rows)
        else:
            if role=='all':
                role=None
            if role not in {None,'student','teacher'}:
                return jsonify({'error':'validation_error','message':'A szerepkör student, teacher vagy all legyen.'}),400
            rows=service.get_all_users(include_inactive,search=query,role=role,limit=limit,offset=offset,include_admin=False)
            total=service.count_users(include_inactive,search=query,role=role,include_admin=False)
        return jsonify(to_json_value(rows)), 200, {'X-Total-Count':str(total),'X-Page-Limit':str(max(1,min(limit,1000))),'X-Page-Offset':str(max(0,offset))}
    except ValueError as exc:
        return jsonify({'error':'validation_error','message':str(exc)}),400

@user_bp.post('/')
@require_auth('admin')
def create_user():
    data=request.get_json(silent=True) or {}
    try:
        role=data.get('role','student')
        user_id=service.create_user(data.get('name'),data.get('neptun'),role,data.get('email'),data.get('password'))
        audit.record(g.identity['user_id'],'user_created','user',user_id,f'{role} felhasználó létrehozva.')
        return jsonify({'id':user_id}),201
    except ValueError as exc:
        return jsonify({'error':'validation_error','message':str(exc)}),400

@user_bp.get('/<int:user_id>')
@require_auth('admin','teacher')
def get_user(user_id):
    user=service.get_user(user_id)
    if not user:
        return jsonify({'error':'not_found'}),404
    if g.identity['role']=='teacher':
        if user.get('role')!='student' or not any(
            item['id']==user_id
            for item in service.list_students_for_teacher(g.identity['user_id'],limit=1000)
        ):
            return jsonify({'error':'not_found'}),404
    elif user.get('role')=='admin':
        return jsonify({'error':'not_found'}),404
    return jsonify(to_json_value(user))

@user_bp.patch('/<int:user_id>')
@require_auth('admin')
def update_user(user_id):
    data=request.get_json(silent=True) or {}
    try:
        user=service.update_user(user_id,name=data.get('name'),neptun=data.get('neptun'),
                                 email=data.get('email'),role=data.get('role'))
        audit.record(g.identity['user_id'],'user_updated','user',user_id,'Felhasználói adatok módosítva.')
        return jsonify(to_json_value(user))
    except ValueError as exc:
        return jsonify({'error':'validation_error','message':str(exc)}),400

@user_bp.post('/<int:user_id>/toggle')
@require_auth('admin')
def toggle(user_id):
    try:
        active=service.toggle_active(user_id)
        audit.record(g.identity['user_id'],'user_activated' if active else 'user_deactivated',
                     'user',user_id,'Felhasználói aktivitás módosítva.')
        return jsonify({'status':'ok','active':active})
    except ValueError as exc:
        return jsonify({'error':'not_found','message':str(exc)}),404

@user_bp.post('/<int:user_id>/assign_card')
@require_auth('admin')
def assign_card(user_id):
    data=request.get_json(silent=True) or {}
    try:
        service.assign_card(user_id,data.get('card_id'),g.identity['user_id'])
        audit.record(g.identity['user_id'],'card_assigned','user',user_id,'NFC-kártya hozzárendelve.')
        return jsonify({'status':'ok'})
    except ValueError as exc:
        return jsonify({'error':'validation_error','message':str(exc)}),400

@user_bp.delete('/<int:user_id>/card')
@require_auth('admin')
def unassign_card(user_id):
    try:
        removed=service.unassign_card(user_id,g.identity['user_id'])
        if removed:
            audit.record(g.identity['user_id'],'card_unassigned','user',user_id,'NFC-kártya hozzárendelése megszüntetve.')
        return jsonify({'status':'removed' if removed else 'no_card'})
    except ValueError as exc:
        return jsonify({'error':'not_found','message':str(exc)}),404

@user_bp.delete('/<int:user_id>')
@require_auth('admin')
def delete_user(user_id):
    try:
        result=service.delete_user(user_id,g.identity['user_id'])
        audit.record(g.identity['user_id'],'user_archived','user',user_id,'Felhasználó archiválva, kártyája felszabadítva.')
        return jsonify(result)
    except ValueError as exc:
        return jsonify({'error':'not_found','message':str(exc)}),404

@user_bp.get('/<int:user_id>/card-history')
@require_auth('admin')
def card_history(user_id):
    return jsonify(to_json_value(service.card_history(user_id,request.args.get('limit',100,type=int))))

@user_bp.post('/bulk-toggle')
@require_auth('admin')
def bulk_toggle():
    data=request.get_json(silent=True) or {}
    ids=data.get('user_ids')
    if not isinstance(ids,list) or not ids or len(ids)>500 or not all(isinstance(item,int) for item in ids):
        return jsonify({'error':'validation_error','message':'1–500 egész azonosító szükséges.'}),400
    changed=[];missing=[]
    for user_id in dict.fromkeys(ids):
        try:
            active=service.toggle_active(user_id)
            changed.append({'id':user_id,'active':active})
        except ValueError:
            missing.append(user_id)
    audit.record(g.identity['user_id'],'users_bulk_toggled','user_batch',None,
                 f'{len(changed)} fiók aktivitása módosult.')
    return jsonify({'updated':changed,'not_found':missing})

