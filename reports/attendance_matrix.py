from database.connection import Database

class AttendanceMatrixReport:
    def __init__(self,db=None):
        self.db=db or Database()

    def build(self,course_id,*,include_withdrawn=False):
        with self.db.cursor() as cursor:
            cursor.execute('SELECT id,code,name FROM courses WHERE id=%s',(course_id,))
            course=cursor.fetchone()
            if not course:
                raise ValueError('A kurzus nem található.')
            cursor.execute(
                'SELECT id,title,starts_at FROM course_sessions WHERE course_id=%s '
                "AND status='closed' ORDER BY starts_at,id",(course_id,)
            )
            sessions=cursor.fetchall()
            enrollment_query=(
                'SELECT u.id user_id,u.name,u.neptun,e.enrollment_status '
                'FROM enrollments e JOIN users u ON u.id=e.user_id WHERE e.course_id=%s'
            )
            if not include_withdrawn:
                enrollment_query+=" AND e.enrollment_status='active'"
            enrollment_query+=' ORDER BY u.name,u.neptun'
            cursor.execute(enrollment_query,(course_id,))
            students=cursor.fetchall()
            cursor.execute(
                'SELECT a.user_id,a.session_id,a.status,a.marked_at,a.method '
                'FROM attendance_records a JOIN course_sessions s ON s.id=a.session_id '
                'WHERE s.course_id=%s AND s.status=\'closed\'',(course_id,)
            )
            attendance=cursor.fetchall()
        values={(item['user_id'],item['session_id']):item for item in attendance}
        matrix=[]
        totals={'present':0,'late':0,'absent':0,'excused':0}
        for student in students:
            cells=[]
            counts={'present':0,'late':0,'absent':0,'excused':0,'unknown':0}
            for session in sessions:
                record=values.get((student['user_id'],session['id']))
                status=record['status'] if record else 'unknown'
                cells.append({'session_id':session['id'],'date':session['starts_at'],
                              'status':status,'marked_at':record['marked_at'] if record else None,
                              'method':record['method'] if record else None})
                counts[status]=counts.get(status,0)+1
                if status in totals:
                    totals[status]+=1
            total=len(sessions)
            attended=counts['present']+counts['late']
            matrix.append({'user_id':student['user_id'],'name':student['name'],
                'neptun':student['neptun'],'enrollment_status':student['enrollment_status'],
                'attendance':cells,'counts':counts,
                'attendance_percent':round(100*attended/total,1) if total else 0.0})
        return {'course':course,'sessions':sessions,'students':matrix,
                'totals':totals,'session_count':len(sessions),'student_count':len(matrix)}

    @staticmethod
    def csv_rows(report):
        header=['Neptun-kód','Hallgató']+[str(item['starts_at']) for item in report['sessions']]
        header.extend(['Jelen','Késett','Hiányzott','Igazolt','Jelenléti arány'])
        rows=[]
        for student in report['students']:
            row=[student.get('neptun') or '',student['name']]
            row.extend(item['status'] for item in student['attendance'])
            counts=student['counts']
            row.extend([counts['present'],counts['late'],counts['absent'],counts['excused'],
                        student['attendance_percent']])
            rows.append(row)
        return header,rows

    @staticmethod
    def summarize_student(student):
        counts = student.get('counts') or {}
        total = sum(int(counts.get(key, 0) or 0) for key in
                    ('present', 'late', 'absent', 'excused', 'unknown'))
        attended = int(counts.get('present', 0) or 0) + int(counts.get('late', 0) or 0)
        excused = int(counts.get('excused', 0) or 0)
        considered = max(0, total - excused)
        return {
            'user_id': student.get('user_id'),
            'name': student.get('name', ''),
            'neptun': student.get('neptun'),
            'attended': attended,
            'missed': int(counts.get('absent', 0) or 0),
            'excused': excused,
            'unknown': int(counts.get('unknown', 0) or 0),
            'attendance_percent': round(100 * attended / considered, 1) if considered else 0.0,
        }

    @classmethod
    def filter_students(cls, report, *, minimum_percent=None, maximum_percent=None,
                        search=None, sort='name'):
        rows = [cls.summarize_student(item) | item for item in report.get('students', [])]
        if minimum_percent is not None:
            rows = [item for item in rows if item['attendance_percent'] >= float(minimum_percent)]
        if maximum_percent is not None:
            rows = [item for item in rows if item['attendance_percent'] <= float(maximum_percent)]
        if search:
            needle = str(search).strip().casefold()
            rows = [item for item in rows if needle in str(item.get('name', '')).casefold()
                    or needle in str(item.get('neptun') or '').casefold()]
        keys = {
            'name': lambda row: str(row.get('name') or '').casefold(),
            'attendance': lambda row: row['attendance_percent'],
            'missed': lambda row: row['missed'],
            'neptun': lambda row: str(row.get('neptun') or '').casefold(),
        }
        rows.sort(key=keys.get(sort, keys['name']))
        return rows

    @staticmethod
    def session_summary(report):

        output = []
        students = report.get('students', [])
        for session in report.get('sessions', []):
            counts = {'present': 0, 'late': 0, 'absent': 0, 'excused': 0, 'unknown': 0}
            for student in students:
                cell = next((item for item in student.get('attendance', [])
                             if item.get('session_id') == session.get('id')), None)
                status = cell.get('status', 'unknown') if cell else 'unknown'
                counts[status] = counts.get(status, 0) + 1
            known = len(students) - counts['unknown']
            attended = counts['present'] + counts['late']
            output.append({
                'session_id': session.get('id'),
                'title': session.get('title'),
                'starts_at': session.get('starts_at'),
                'counts': counts,
                'marked_percent': round(100 * known / len(students), 1) if students else 0.0,
                'attendance_percent': round(100 * attended / known, 1) if known else 0.0,
            })
        return output

    @classmethod
    def risk_list(cls, report, threshold=75.0):
        threshold = max(0.0, min(float(threshold), 100.0))
        return [row for row in cls.filter_students(report, sort='attendance')
                if row['attendance_percent'] < threshold]

    @staticmethod
    def json_safe(report):
        from datetime import date, datetime
        def convert(value):
            if isinstance(value, (date, datetime)):
                return value.isoformat()
            if isinstance(value, dict):
                return {key: convert(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [convert(item) for item in value]
            return value
        return convert(report)

    @classmethod
    def extended_csv_rows(cls, report, *, include_email=False):
        header, rows = cls.csv_rows(report)
        if include_email:
            header.insert(2, 'E-mail')
        for student, row in zip(report.get('students', []), rows):
            if include_email:
                row.insert(2, student.get('email') or '')
        return header, rows

    @staticmethod
    def validate_threshold(value):
        try:
            threshold = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError('A jelenléti küszöb szám legyen.') from exc
        if not 0 <= threshold <= 100:
            raise ValueError('A jelenléti küszöb 0 és 100 közé essen.')
        return threshold

    @classmethod
    def course_overview(cls, report, threshold=75.0):
        threshold = cls.validate_threshold(threshold)
        students = [cls.summarize_student(item) for item in report.get('students', [])]
        sessions = report.get('sessions', [])
        values = [item['attendance_percent'] for item in students]
        risk = [item for item in students if item['attendance_percent'] < threshold]
        return {
            'course': report.get('course'),
            'students': len(students),
            'sessions': len(sessions),
            'threshold': threshold,
            'at_risk_count': len(risk),
            'average_attendance_percent': round(sum(values) / len(values), 1) if values else 0.0,
            'best_attendance_percent': max(values) if values else 0.0,
            'lowest_attendance_percent': min(values) if values else 0.0,
            'at_risk': risk,
            'sessions_detail': cls.session_summary(report),
        }

    @classmethod
    def attendance_trend(cls, report, *, window=5):
        window = max(1, min(int(window), 30))
        recent = cls.session_summary(report)[-window:]
        values = [item['attendance_percent'] for item in recent]
        if len(values) < 2:
            direction = 'insufficient_data'
            change = 0.0
        else:
            change = round(values[-1] - values[0], 1)
            direction = 'improving' if change > 0 else 'declining' if change < 0 else 'stable'
        return {'direction': direction, 'change_percentage_points': change,
                'sessions': recent, 'window_size': len(recent)}

    @staticmethod
    def validate_session_selection(report, session_ids):
        available = {int(item['id']) for item in report.get('sessions', [])}
        selected = []
        for raw in session_ids:
            try:
                value = int(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError('Az alkalomazonosító csak egész szám lehet.') from exc
            if value not in available:
                raise ValueError(f'Ismeretlen kurzusalkalom: {value}.')
            if value not in selected:
                selected.append(value)
        return selected

    @classmethod
    def select_sessions(cls, report, session_ids):
        selected = set(cls.validate_session_selection(report, session_ids))
        result = dict(report)
        result['sessions'] = [item for item in report.get('sessions', [])
                              if int(item['id']) in selected]
        students = []
        for original in report.get('students', []):
            student = dict(original)
            student['attendance'] = [cell for cell in original.get('attendance', [])
                                     if int(cell['session_id']) in selected]
            counts = {'present': 0, 'late': 0, 'absent': 0, 'excused': 0, 'unknown': 0}
            for cell in student['attendance']:
                counts[cell['status']] = counts.get(cell['status'], 0) + 1
            student['counts'] = counts
            attended = counts['present'] + counts['late']
            student['attendance_percent'] = round(100 * attended / len(selected), 1) if selected else 0.0
            students.append(student)
        result['students'] = students
        result['session_count'] = len(result['sessions'])
        result['student_count'] = len(students)
        return result

    @staticmethod
    def plain_text_summary(report, threshold=75.0):
        overview = AttendanceMatrixReport.course_overview(report, threshold)
        course = overview.get('course') or {}
        code = course.get('code', 'ismeretlen kurzus')
        return '\n'.join([
            f"Kurzus: {code} – {course.get('name', '')}",
            f"Hallgatók száma: {overview['students']}",
            f"Megtartott alkalmak: {overview['sessions']}",
            f"Átlagos jelenlét: {overview['average_attendance_percent']:.1f}%",
            f"Küszöb alatti hallgatók: {overview['at_risk_count']} "
            f"({overview['threshold']:.1f}% alatt)",
        ])

    @staticmethod
    def status_label(status):
        labels = {'present': 'Jelen', 'late': 'Késett', 'absent': 'Hiányzott',
                  'excused': 'Igazolt', 'unknown': 'Nincs rögzítve'}
        return labels.get(status, 'Ismeretlen')

    @classmethod
    def localized_csv_rows(cls, report):
        header, rows = cls.csv_rows(report)
        status_column_count = len(report.get('sessions', []))
        for row in rows:
            for index in range(2, 2 + status_column_count):
                row[index] = cls.status_label(row[index])
        return header, rows
