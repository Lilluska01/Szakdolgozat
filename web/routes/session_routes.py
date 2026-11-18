from functools import wraps
from flask import Blueprint,jsonify,request,g
from services.session_service import SessionService
from services.course_service import CourseService
from services.audit_service import AuditService
from services.serialization import to_json_value
from services.attendance_import_service import AttendanceImportService
from services.room_service import RoomService
from web.auth import require_auth

session_bp=Blueprint('sessions',__name__)
sessions=SessionService()
courses=CourseService()
audit=AuditService()
imports=AttendanceImportService(session_service=sessions)
rooms_service=RoomService()

def require_course_owner(view):
    @wraps(view)
    def wrapped(course_id,*args,**kwargs):
        if g.identity.get('role')=='admin':
            return view(course_id,*args,**kwargs)
        course=courses.get_course(course_id)
        if not course or course.get('teacher_id')!=g.identity.get('user_id'):
            return jsonify({'error':'forbidden','message':'Csak a saját kurzus kezelhető.'}),403
        return view(course_id,*args,**kwargs)
    return wrapped

def require_session_owner(view):
    @wraps(view)
    def wrapped(session_id,*args,**kwargs):
        if g.identity.get('role')=='admin':
            return view(session_id,*args,**kwargs)
        session=sessions.get_session(session_id)
        course=courses.get_course(session['course_id']) if session else None
        if not course or course.get('teacher_id')!=g.identity.get('user_id'):
            return jsonify({'error':'forbidden','message':'Csak a saját kurzus alkalma kezelhető.'}),403
        return view(session_id,*args,**kwargs)
    return wrapped

@session_bp.get('/')
@require_auth('admin','teacher')
def list_sessions():
    try:
        teacher_id=g.identity['user_id'] if g.identity['role']=='teacher' else None
        rows=sessions.list_sessions(
            course_id=request.args.get('course_id',type=int),
            state=request.args.get('state'),
            from_time=request.args.get('from'),
            to_time=request.args.get('to'),
            limit=request.args.get('limit',100,type=int),
            offset=request.args.get('offset',0,type=int),
            teacher_id=teacher_id,
        )
        return jsonify(to_json_value(rows))
    except ValueError as exc:
        return jsonify({'error':'validation_error','message':str(exc)}),400

@session_bp.post('/courses/<int:course_id>')
@require_auth('admin','teacher')
@require_course_owner
def create_session(course_id):
    data=request.get_json(silent=True) or {}
    try:
        session_id=sessions.create_session(
            course_id=course_id,starts_at=data.get('starts_at'),ends_at=data.get('ends_at'),
            title=data.get('title'),room=data.get('room'),
            late_after_minutes=int(data.get('late_after_minutes',10)),
            created_by=g.identity['user_id'],
        )
        audit.record(g.identity['user_id'],'session_created','session',session_id,
                     f'Kurzusalkalom létrehozva: {course_id}.')
        return jsonify({'id':session_id,'status':'planned'}),201
    except (ValueError,TypeError) as exc:
        return jsonify({'error':'validation_error','message':str(exc)}),400

@session_bp.post('/courses/<int:course_id>/series')
@require_auth('admin','teacher')
@require_course_owner
def create_series(course_id):
    data=request.get_json(silent=True) or {}
    try:
        ids=sessions.create_series(
            course_id=course_id,first_start=data.get('first_start'),
            duration_minutes=int(data.get('duration_minutes',90)),weeks=int(data.get('weeks',1)),
            room=data.get('room'),title=data.get('title'),
            late_after_minutes=int(data.get('late_after_minutes',10)),
            created_by=g.identity['user_id'],
        )
        audit.record(g.identity['user_id'],'session_series_created','course',course_id,
                     f'{len(ids)} kurzusalkalom ütemezve.')
        return jsonify({'session_ids':ids,'count':len(ids)}),201
    except (ValueError,TypeError) as exc:
        return jsonify({'error':'validation_error','message':str(exc)}),400

@session_bp.get('/<int:session_id>')
@require_auth('admin','teacher')
@require_session_owner
def get_roster(session_id):
    try:
        result=sessions.get_roster(session_id,search=request.args.get('q'),
            status=request.args.get('status'),limit=request.args.get('limit',500,type=int),
            offset=request.args.get('offset',0,type=int))
        result['summary']=sessions.attendance_summary(session_id)
        return jsonify(to_json_value(result))
    except ValueError as exc:
        return jsonify({'error':'not_found_or_invalid','message':str(exc)}),404

@session_bp.post('/<int:session_id>/open')
@require_auth('admin','teacher')
@require_session_owner
def open_session(session_id):
    return _transition(session_id,'open')

@session_bp.post('/<int:session_id>/close')
@require_auth('admin','teacher')
@require_session_owner
def close_session(session_id):
    return _transition(session_id,'closed')

@session_bp.post('/<int:session_id>/cancel')
@require_auth('admin')
@require_session_owner
def cancel_session(session_id):
    return _transition(session_id,'cancelled')

@session_bp.delete('/<int:session_id>')
@require_auth('admin')
def delete_session(session_id):
    try:
        sessions.delete_session(session_id)
        audit.record(g.identity['user_id'],'session_deleted','session',session_id,
                     'Kurzusalkalom és kapcsolódó jelenléti adatok törölve.')
        return jsonify({'id':session_id,'deleted':True})
    except ValueError as exc:
        return jsonify({'error':'not_found','message':str(exc)}),404

def _transition(session_id,target):
    try:
        sessions.transition(session_id,target)
        audit.record(g.identity['user_id'],'session_'+target,'session',session_id,
                     f'A kurzusalkalom állapota erre változott: {target}.')
        return jsonify({'id':session_id,'status':target})
    except ValueError as exc:
        return jsonify({'error':'invalid_transition','message':str(exc)}),409

@session_bp.post('/<int:session_id>/scan')
@require_auth('admin','teacher')
@require_session_owner
def scan_for_session(session_id):
    data=request.get_json(silent=True) or {}
    result=sessions.record_nfc(session_id,data.get('card_id'))
    return jsonify(to_json_value(result)),200 if result['status'] in {'PRESENT','LATE','ALREADY_MARKED'} else 400

@session_bp.put('/<int:session_id>/attendance/<int:user_id>')
@require_auth('admin','teacher')
@require_session_owner
def set_attendance(session_id,user_id):
    data=request.get_json(silent=True) or {}
    try:
        result=sessions.mark_attendance(session_id,user_id,data.get('status'),
            g.identity['user_id'],data.get('note'))
        audit.record(g.identity['user_id'],'attendance_marked','attendance',
                     f'{session_id}:{user_id}',f"Jelenléti állapot beállítva: {result['status']}.")
        return jsonify(to_json_value(result))
    except ValueError as exc:
        return jsonify({'error':'invalid_attendance','message':str(exc)}),400

@session_bp.post('/<int:session_id>/attendance/bulk')
@require_auth('admin','teacher')
@require_session_owner
def bulk_attendance(session_id):
    data=request.get_json(silent=True) or {}
    try:
        result=sessions.mark_bulk(session_id,data.get('changes'),g.identity['user_id'],data.get('note'))
        audit.record(g.identity['user_id'],'attendance_bulk_marked','session',session_id,
                     f"{result['updated']} jelenléti bejegyzés módosult.")
        return jsonify(result)
    except (ValueError,TypeError) as exc:
        return jsonify({'error':'validation_error','message':str(exc)}),400

@session_bp.get('/<int:session_id>/attendance/<int:user_id>/history')
@require_auth('admin','teacher')
@require_session_owner
def attendance_history(session_id,user_id):
    rows=sessions.attendance_history(session_id,user_id,request.args.get('limit',100,type=int))
    return jsonify(to_json_value(rows))

@session_bp.post('/<int:session_id>/attendance/import/preview')
@require_auth('admin','teacher')
@require_session_owner
def preview_attendance_import(session_id):
    uploaded=request.files.get('file')
    if uploaded is None:
        return jsonify({'error':'file_required'}),400
    try:
        result=imports.preview(session_id,uploaded.stream.read(1_000_001))
        return jsonify(result)
    except ValueError as exc:
        return jsonify({'error':'invalid_import','message':str(exc)}),400

@session_bp.post('/<int:session_id>/attendance/import/commit')
@require_auth('admin','teacher')
@require_session_owner
def commit_attendance_import(session_id):
    data=request.get_json(silent=True) or {}
    try:
        result=imports.commit(session_id,data.get('preview',{}),g.identity['user_id'],
                             data.get('reason','CSV-import'))
        audit.record(g.identity['user_id'],'attendance_imported','session',session_id,
                     f"{result['imported_rows']} jelenléti sor importálva.")
        return jsonify(result)
    except ValueError as exc:
        return jsonify({'error':'invalid_import','message':str(exc)}),400

@session_bp.get('/rooms')
@require_auth('admin','teacher')
def rooms():
    from services.session_service import SessionService as SessionTools
    starts=request.args.get('from');ends=request.args.get('to')
    if not starts or not ends:
        return jsonify({'error':'validation_error','message':'from és to időpont szükséges.'}),400
    try:
        result=rooms_service.availability(request.args.get('room',''),
            SessionTools._as_datetime(starts),SessionTools._as_datetime(ends),
            request.args.get('exclude_session_id',type=int))
        return jsonify(to_json_value(result))
    except ValueError as exc:
        return jsonify({'error':'validation_error','message':str(exc)}),400
