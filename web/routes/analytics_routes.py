from flask import Blueprint, jsonify, request, g
from services.analytics_service import AnalyticsService
from services.serialization import to_json_value
from web.auth import require_auth

analytics_bp=Blueprint('analytics',__name__)
service=AnalyticsService()

@analytics_bp.get('/courses')
@require_auth('admin','teacher')
def course_summary():
    return jsonify(to_json_value(service.attendance_by_course(
        start_date=request.args.get('from'),end_date=request.args.get('to'),
        teacher_id=g.identity['user_id'] if g.identity['role']=='teacher' else None)))

@analytics_bp.get('/students')
@require_auth('admin','teacher')
def student_summary():
    return jsonify(to_json_value(service.student_attendance(
        course_id=request.args.get('course_id',type=int),
        search=request.args.get('q'),
        limit=request.args.get('limit',100,type=int),
        offset=request.args.get('offset',0,type=int),
        teacher_id=g.identity['user_id'] if g.identity['role']=='teacher' else None)))

@analytics_bp.get('/daily-access')
@require_auth('admin')
def daily_access():
    return jsonify(to_json_value(service.daily_access_volume(request.args.get('days',30,type=int))))

@analytics_bp.get('/busy-hours')
@require_auth('admin')
def busy_hours():
    return jsonify(to_json_value(service.busiest_hours(request.args.get('days',30,type=int))))
