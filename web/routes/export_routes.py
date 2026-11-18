import csv
import io
from flask import Blueprint, jsonify, request, Response
from services.user_service import UserService
from services.access_service import AccessService
from services.session_service import SessionService
from web.auth import require_auth

export_bp=Blueprint('exports',__name__)
users=UserService(); access=AccessService(); sessions=SessionService()

def csv_response(file_name,header,rows):
    output=io.StringIO(newline='')
    writer=csv.writer(output)
    writer.writerow(header)
    writer.writerows(rows)
    body='\ufeff'+output.getvalue()
    return Response(body,mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition':f'attachment; filename="{file_name}"'})

@export_bp.get('/users.csv')
@require_auth('admin')
def export_users():
    records=users.get_all_users(include_admin=False,include_archived=False)
    header=['ID','Név','E-mail','Neptun-kód','Kártya UID','Szerepkör','Aktív','Bent','Utolsó esemény']
    rows=[[row.get('id'),row.get('name'),row.get('email'),row.get('neptun'),row.get('card_id'),
           row.get('role'),bool(row.get('active')),bool(row.get('is_inside')),row.get('last_seen')]
          for row in records]
    return csv_response('felhasznalok.csv',header,rows)

@export_bp.get('/access.csv')
@require_auth('admin')
def export_access():
    limit=request.args.get('limit',500,type=int)
    records=access.get_last_logs(limit)
    header=['ID','Hallgató','Neptun-kód','Kártya UID','Esemény','Forrás','Időpont']
    rows=[[row.get('id'),row.get('name'),row.get('neptun'),row.get('card_id'),row.get('action'),
           row.get('source'),row.get('timestamp')] for row in records]
    return csv_response('belepesek.csv',header,rows)

@export_bp.get('/sessions/<int:session_id>.csv')
@require_auth('admin','teacher')
def export_session(session_id):
    try:
        session=sessions.get_session(session_id)
        if not session:
            return jsonify({'error':'not_found','message':'Az alkalom nem található.'}),404
        from flask import g
        from services.course_service import CourseService
        course=CourseService().get_course(session['course_id'])
        if g.identity['role']=='teacher' and course.get('teacher_id')!=g.identity['user_id']:
            return jsonify({'error':'forbidden'}),403
        records=sessions.get_roster(session_id)['students']
    except ValueError as exc:
        return jsonify({'error':'not_found','message':str(exc)}),404
    header=['Név','Neptun-kód','Állapot','Időpont','Módszer','Megjegyzés']
    rows=[[row.get('name'),row.get('neptun'),row.get('status'),row.get('marked_at'),
           row.get('method'),row.get('note')] for row in records]
    return csv_response(f'jelenlet-{session_id}.csv',header,rows)

@export_bp.get('/templates/students.csv')
@require_auth('admin')
def student_import_template():
    body='Név;Neptun-kód;E-mail\\nMinta Hallgató;ABC123;minta@example.edu\\n'
    return csv_response('hallgatok-minta.csv',['Név','Neptun-kód','E-mail'],[['Minta Hallgató','ABC123','minta@example.edu']])
@export_bp.get('/calendar.ics')
@require_auth('admin','teacher')
def export_calendar():
    from flask import Response, g
    from datetime import datetime,timedelta
    from services.room_service import RoomService
    from services.calendar_export_service import CalendarExportService
    start=datetime.now()-timedelta(days=30);end=datetime.now()+timedelta(days=180)
    teacher_id=g.identity['user_id'] if g.identity['role']=='teacher' else None
    events=RoomService().calendar(start,end,teacher_id)
    body=CalendarExportService().render(events)
    return Response(body,mimetype='text/calendar; charset=utf-8',
                    headers={'Content-Disposition':'attachment; filename=kurzusalkalmak.ics'})

@export_bp.get('/courses/<int:course_id>/attendance-matrix.csv')
@require_auth('admin','teacher')
def export_course_matrix(course_id):
    from services.course_service import CourseService
    from reports.attendance_matrix import AttendanceMatrixReport
    identity=__import__('flask').g.identity
    course=CourseService().get_course(course_id)
    if not course:
        return jsonify({'error':'not_found'}),404
    if identity['role']=='teacher' and course.get('teacher_id')!=identity['user_id']:
        return jsonify({'error':'forbidden'}),403
    try:
        report=AttendanceMatrixReport().build(course_id)
        header,rows=AttendanceMatrixReport.csv_rows(report)
        return csv_response(f"{course['code']}-jelenleti-matrix.csv",header,rows)
    except ValueError as exc:
        return jsonify({'error':'report_error','message':str(exc)}),400
