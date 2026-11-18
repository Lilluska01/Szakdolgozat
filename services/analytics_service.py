from database.connection import Database

class AnalyticsService:
    def __init__(self, db=None):
        self.db = db or Database()

    def attendance_by_course(self, *, start_date=None, end_date=None, teacher_id=None):
        query = (
            'SELECT c.id course_id,c.code,c.name,COUNT(DISTINCT s.id) sessions,'
            'COUNT(a.id) enrolled_marks,SUM(a.status=\'present\') present_count,'
            'SUM(a.status=\'late\') late_count,SUM(a.status=\'absent\') absent_count,'
            'SUM(a.status=\'excused\') excused_count FROM courses c '
            'LEFT JOIN course_sessions s ON s.course_id=c.id AND s.status<>\'cancelled\' '
            'AND (%s IS NULL OR s.starts_at >= %s) AND (%s IS NULL OR s.starts_at < %s) '
            'LEFT JOIN attendance_records a ON a.session_id=s.id '
            'WHERE c.active=1'
        )
        params = [start_date,start_date,end_date,end_date]
        if teacher_id is not None:
            query+=' AND c.teacher_id=%s';params.append(teacher_id)
        query+=' GROUP BY c.id,c.code,c.name ORDER BY c.code'
        with self.db.cursor() as cursor:
            cursor.execute(query,tuple(params))
            return cursor.fetchall()

    def student_attendance(self, *, course_id=None, search=None, limit=100, offset=0,teacher_id=None):
        query = (
            'SELECT u.id user_id,u.name,u.neptun,c.id course_id,c.code,c.name course_name,'
            'COUNT(a.id) total_sessions,SUM(a.status=\'present\') present_count,'
            'SUM(a.status=\'late\') late_count,SUM(a.status=\'absent\') absent_count,'
            'SUM(a.status=\'excused\') excused_count FROM users u '
            'JOIN enrollments e ON e.user_id=u.id AND e.enrollment_status=\'active\' '
            'JOIN courses c ON c.id=e.course_id LEFT JOIN course_sessions s '
            'ON s.course_id=c.id AND s.status<>\'cancelled\' '
            'LEFT JOIN attendance_records a ON a.session_id=s.id AND a.user_id=u.id '
            'WHERE u.role=\'student\' AND u.active=1'
        )
        params=[]
        if course_id is not None:
            query += ' AND c.id=%s'; params.append(course_id)
        if teacher_id is not None:
            query += ' AND c.teacher_id=%s'; params.append(teacher_id)
        if search:
            query += ' AND (u.name LIKE %s OR u.neptun LIKE %s)'
            pattern='%'+search[:80]+'%'; params.extend((pattern,pattern))
        query += (' GROUP BY u.id,u.name,u.neptun,c.id,c.code,c.name '
                  'ORDER BY c.code,u.name LIMIT %s OFFSET %s')
        params.extend((max(1,min(int(limit),500)),max(0,int(offset))))
        with self.db.cursor() as cursor:
            cursor.execute(query,tuple(params))
            return cursor.fetchall()

    def daily_access_volume(self, days=30):
        days=max(1,min(int(days),365))
        with self.db.cursor() as cursor:
            cursor.execute(
                'SELECT DATE(timestamp) day,COUNT(*) scans,'
                'SUM(action=\'ENTRY\') entries,SUM(action=\'EXIT\') exits '
                'FROM access_logs WHERE timestamp >= DATE_SUB(CURDATE(),INTERVAL %s DAY) '
                'GROUP BY DATE(timestamp) ORDER BY day', (days,)
            )
            return cursor.fetchall()

    def busiest_hours(self, days=30):
        days=max(1,min(int(days),365))
        with self.db.cursor() as cursor:
            cursor.execute(
                'SELECT HOUR(timestamp) hour,COUNT(*) scans '
                'FROM access_logs WHERE action=\'ENTRY\' '
                'AND timestamp >= DATE_SUB(CURDATE(),INTERVAL %s DAY) '
                'GROUP BY HOUR(timestamp) ORDER BY hour', (days,)
            )
            return cursor.fetchall()
