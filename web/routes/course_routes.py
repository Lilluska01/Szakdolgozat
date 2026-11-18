from flask import Blueprint,jsonify,request,g
from services.course_service import CourseService
from services.serialization import to_json_value
from services.audit_service import AuditService
from web.auth import require_auth

course_bp=Blueprint('courses',__name__)
service=CourseService();audit=AuditService()

def owns_course(course_id):
    if g.identity['role']=='admin':
        return True
    course=service.get_course(course_id)
    return bool(course and course.get('teacher_id')==g.identity['user_id'])

@course_bp.get('/')
@require_auth('admin','teacher')
def list_courses():
    teacher_id=g.identity['user_id'] if g.identity['role']=='teacher' else None
    return jsonify(to_json_value(service.list_courses(teacher_id=teacher_id,
        search=request.args.get('q'),limit=request.args.get('limit',500,type=int),
        offset=request.args.get('offset',0,type=int))))

@course_bp.post('/')
@require_auth('admin')
def create_course():
    data=request.get_json(silent=True) or {}
    try:
        course_id=service.create_course(data.get('code'),data.get('name'),
            data.get('teacher_id'),data.get('description'))
        audit.record(g.identity['user_id'],'course_created','course',course_id,'Kurzus létrehozva.')
        return jsonify({'id':course_id}),201
    except ValueError as exc:
        return jsonify({'error':'validation_error','message':str(exc)}),400

@course_bp.patch('/<int:course_id>')
@require_auth('admin')
def update_course(course_id):
    data=request.get_json(silent=True) or {}
    try:
        result=service.update_course(course_id,code=data.get('code'),name=data.get('name'),
            description=data.get('description'),teacher_id=data.get('teacher_id'),
            teacher_id_supplied='teacher_id' in data)
        audit.record(g.identity['user_id'],'course_updated','course',course_id,'Kurzusadatok módosítva.')
        return jsonify(to_json_value(result))
    except ValueError as exc:
        return jsonify({'error':'not_found_or_invalid','message':str(exc)}),400

@course_bp.get('/<int:course_id>/students')
@require_auth('admin','teacher')
def list_students(course_id):
    if not owns_course(course_id):
        return jsonify({'error':'forbidden'}),403
    return jsonify(to_json_value(service.list_students(course_id,
        search=request.args.get('q'),limit=request.args.get('limit',500,type=int),
        offset=request.args.get('offset',0,type=int))))

@course_bp.post('/<int:course_id>/students/<int:user_id>')
@require_auth('admin')
def enroll(course_id,user_id):
    try:
        created=service.enroll(course_id,user_id)
        audit.record(g.identity['user_id'],'student_enrolled','course',course_id,
                     f'Felhasználó felvéve: {user_id}.')
        return jsonify({'status':'enrolled' if created else 'already_enrolled'}),201 if created else 200
    except ValueError as exc:
        return jsonify({'error':'validation_error','message':str(exc)}),400

@course_bp.post('/<int:course_id>/students/bulk')
@require_auth('admin')
def enroll_many(course_id):
    data=request.get_json(silent=True) or {}
    try:
        result=service.enroll_many(course_id,data.get('user_ids'))
        audit.record(g.identity['user_id'],'students_bulk_enrolled','course',course_id,
                     f"{len(result['created'])} hallgató felvéve.")
        return jsonify(result),201
    except (ValueError,TypeError) as exc:
        return jsonify({'error':'validation_error','message':str(exc)}),400

@course_bp.delete('/<int:course_id>/students/<int:user_id>')
@require_auth('admin')
def unenroll(course_id,user_id):
    if not service.remove_enrollment(course_id,user_id):
        return jsonify({'error':'not_found'}),404
    audit.record(g.identity['user_id'],'student_unenrolled','course',course_id,
                 f'Felhasználó kurzusfelvétele visszavonva: {user_id}.')
    return jsonify({'status':'removed'})

@course_bp.delete('/<int:course_id>')
@require_auth('admin')
def deactivate_course(course_id):
    try:
        active=service.set_active(course_id,False)
        audit.record(g.identity['user_id'],'course_deactivated','course',course_id,'Kurzus deaktiválva.')
        return jsonify({'id':course_id,'active':active})
    except ValueError as exc:
        return jsonify({'error':'not_found','message':str(exc)}),404
