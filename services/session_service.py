from datetime import datetime, timedelta
from database.connection import Database

ATTENDANCE_STATES = {'absent', 'present', 'late', 'excused'}
SESSION_STATES = {'planned', 'open', 'closed', 'cancelled'}

class SessionService:
    def __init__(self, db=None, clock=None):
        self.db = db or Database()
        self.clock = clock or datetime.now

    def create_session(self, course_id, starts_at, ends_at, title=None, room=None,
                       late_after_minutes=10, created_by=None):
        starts_at = self._as_datetime(starts_at)
        ends_at = self._as_datetime(ends_at)
        if starts_at >= ends_at:
            raise ValueError('Az alkalom befejezési időpontjának a kezdés után kell lennie.')
        if late_after_minutes < 0 or late_after_minutes > 180:
            raise ValueError('A késési türelmi idő 0 és 180 perc közé essen.')
        title = (title or '').strip() or None
        room = (room or '').strip() or None
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('SELECT id FROM courses WHERE id=%s AND active=1 FOR UPDATE', (course_id,))
            if not cursor.fetchone():
                raise ValueError('Az aktív kurzus nem található.')
            cursor.execute(
                "SELECT id FROM course_sessions WHERE course_id=%s "
                "AND status<>'cancelled' AND starts_at < %s AND ends_at > %s LIMIT 1",
                (course_id, ends_at, starts_at),
            )
            if cursor.fetchone():
                raise ValueError('Az időpont átfed egy másik kurzusalkalommal.')
            if room:
                cursor.execute(
                    "SELECT id FROM course_sessions WHERE room=%s AND status<>'cancelled' "
                    'AND starts_at < %s AND ends_at > %s LIMIT 1',
                    (room,ends_at,starts_at),
                )
                if cursor.fetchone():
                    raise ValueError('A terem ebben az időpontban már foglalt.')
            cursor.execute(
                'INSERT INTO course_sessions(course_id,title,starts_at,ends_at,room,late_after_minutes,created_by) '
                'VALUES(%s,%s,%s,%s,%s,%s,%s)',
                (course_id, title, starts_at, ends_at, room, late_after_minutes, created_by),
            )
            session_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO attendance_records(session_id,user_id,status,method) "
                "SELECT %s,e.user_id,'absent','manual' FROM enrollments e "
                "JOIN users u ON u.id=e.user_id WHERE e.course_id=%s "
                "AND e.enrollment_status='active' AND u.active=1",
                (session_id, course_id),
            )
            return session_id

    def list_sessions(self, course_id=None, state=None, from_time=None, to_time=None,
                      limit=100, offset=0, teacher_id=None):
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        if state and state not in SESSION_STATES:
            raise ValueError('Érvénytelen alkalomállapot.')
        query = (
            'SELECT s.id,s.course_id,c.code course_code,c.name course_name,s.title,'
            's.starts_at,s.ends_at,s.room,s.status,s.late_after_minutes,'
            "COUNT(CASE WHEN s.status NOT IN ('planned','open') "
            "OR e.enrollment_status='active' THEN a.id END) roster_size,"
            "SUM(CASE WHEN (s.status NOT IN ('planned','open') "
            "OR e.enrollment_status='active') "
            "AND a.status IN ('present','late') THEN 1 ELSE 0 END) present_count "
            'FROM course_sessions s JOIN courses c ON c.id=s.course_id '
            'LEFT JOIN attendance_records a ON a.session_id=s.id '
            'LEFT JOIN enrollments e ON e.course_id=s.course_id AND e.user_id=a.user_id WHERE 1=1'
        )
        params = []
        if course_id is not None:
            query += ' AND s.course_id=%s'; params.append(course_id)
        if teacher_id is not None:
            query += ' AND c.teacher_id=%s'; params.append(teacher_id)
        if state:
            query += ' AND s.status=%s'; params.append(state)
        if from_time:
            query += ' AND s.starts_at >= %s'; params.append(self._as_datetime(from_time))
        if to_time:
            query += ' AND s.starts_at < %s'; params.append(self._as_datetime(to_time))
        query += (' GROUP BY s.id,s.course_id,c.code,c.name,s.title,s.starts_at,s.ends_at,'
                  's.room,s.status,s.late_after_minutes ORDER BY s.starts_at DESC '
                  'LIMIT %s OFFSET %s')
        params.extend((limit, offset))
        with self.db.cursor() as cursor:
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    def get_session(self, session_id):
        with self.db.cursor() as cursor:
            cursor.execute(
                'SELECT s.*,c.code course_code,c.name course_name FROM course_sessions s '
                'JOIN courses c ON c.id=s.course_id WHERE s.id=%s', (session_id,)
            )
            return cursor.fetchone()

    def transition(self, session_id, target_state):
        if target_state not in {'open', 'closed', 'cancelled'}:
            raise ValueError('Érvénytelen célállapot.')
        allowed = {'open': {'planned'}, 'closed': {'open'}, 'cancelled': {'planned', 'open'}}
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('SELECT id,status FROM course_sessions WHERE id=%s FOR UPDATE', (session_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError('Az alkalom nem található.')
            if row['status'] not in allowed[target_state]:
                raise ValueError(f"Az alkalom nem váltható {row['status']} állapotból {target_state} állapotba.")
            cursor.execute('UPDATE course_sessions SET status=%s WHERE id=%s', (target_state, session_id))
            return target_state

    def delete_session(self, session_id):
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('DELETE FROM course_sessions WHERE id=%s', (session_id,))
            if not cursor.rowcount:
                raise ValueError('Az alkalom nem található.')
            return True

    def get_roster(self, session_id, *, search=None, status=None, limit=500, offset=0):
        session = self.get_session(session_id)
        if not session:
            raise ValueError('Az alkalom nem található.')
        if status and status not in ATTENDANCE_STATES:
            raise ValueError('Érvénytelen jelenléti állapot.')
        query = (
            'SELECT a.id record_id,a.session_id,a.user_id,u.name,u.neptun,u.card_id,'
            'u.email,a.status,a.marked_at,a.method,a.note FROM attendance_records a '
            'JOIN users u ON u.id=a.user_id WHERE a.session_id=%s'
        )
        params = [session_id]
        if session['status'] in {'planned', 'open'}:
            query += (
                " AND EXISTS (SELECT 1 FROM enrollments e WHERE e.course_id=%s "
                "AND e.user_id=a.user_id AND e.enrollment_status='active')"
            )
            params.append(session['course_id'])
        if search:
            query += ' AND (u.name LIKE %s OR u.neptun LIKE %s OR u.email LIKE %s)'
            pattern = '%' + search.strip()[:80] + '%'
            params.extend((pattern, pattern, pattern))
        if status:
            query += ' AND a.status=%s'; params.append(status)
        query += ' ORDER BY u.name,u.neptun LIMIT %s OFFSET %s'
        params.extend((max(1, min(int(limit), 500)), max(0, int(offset))))
        with self.db.cursor() as cursor:
            cursor.execute(query, tuple(params))
            return {'session': session, 'students': cursor.fetchall()}

    def mark_attendance(self, session_id, user_id, status, actor_id, note=None):
        if status not in ATTENDANCE_STATES:
            raise ValueError('Érvénytelen jelenléti állapot.')
        note = (note or '').strip()[:500] or None
        session = self.get_session(session_id)
        if not session:
            raise ValueError('Az alkalom nem található.')
        if session['status'] in {'cancelled', 'closed'}:
            raise ValueError('A lezárt vagy törölt alkalom nem módosítható.')
        now = self.clock()
        marked_at = now if status in {'present', 'late'} else None
        with self.db.cursor(commit=True) as cursor:
            cursor.execute(
                "SELECT u.id FROM users u JOIN enrollments e ON e.user_id=u.id "
                "WHERE u.id=%s AND e.course_id=%s AND e.enrollment_status='active' AND u.active=1",
                (user_id, session['course_id']),
            )
            if not cursor.fetchone():
                raise ValueError('A hallgató nem aktív ezen a kurzuson.')
            cursor.execute('SELECT status FROM attendance_records WHERE session_id=%s AND user_id=%s FOR UPDATE',(session_id,user_id))
            previous=cursor.fetchone()
            cursor.execute('INSERT INTO attendance_history(session_id,user_id,actor_id,previous_status,new_status,source,reason) VALUES(%s,%s,%s,%s,%s,\'manual\',%s)',(session_id,user_id,actor_id,previous['status'] if previous else None,status,note))
            cursor.execute(
                'INSERT INTO attendance_records(session_id,user_id,status,marked_at,marked_by,method,note) '
                'VALUES(%s,%s,%s,%s,%s,\'manual\',%s) ON DUPLICATE KEY UPDATE '
                'status=VALUES(status),marked_at=VALUES(marked_at),marked_by=VALUES(marked_by),'
                'method=VALUES(method),note=VALUES(note)',
                (session_id,user_id,status,marked_at,actor_id,note),
            )
        return {'session_id': session_id, 'user_id': user_id, 'status': status,
                'marked_at': marked_at, 'marked_by': actor_id, 'method': 'manual', 'note': note}

    def record_nfc(self, session_id, card_id):
        card_id = (card_id or '').strip().upper()
        if not card_id:
            return {'status': 'INVALID_CARD'}
        now = self.clock()
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('SELECT * FROM course_sessions WHERE id=%s FOR UPDATE', (session_id,))
            session = cursor.fetchone()
            if not session:
                return {'status': 'SESSION_NOT_FOUND'}
            if session['status'] not in {'planned','open'}:
                return {'status': 'SESSION_CLOSED'}
            if now < session['starts_at']:
                return {'status': 'TOO_EARLY'}
            if now >= session['ends_at']:
                return {'status': 'TOO_LATE'}
            cursor.execute("SELECT id,name FROM users WHERE card_id=%s AND active=1 AND role='student' AND deleted_at IS NULL", (card_id,))
            user = cursor.fetchone()
            if not user:
                return {'status': 'UNKNOWN_CARD'}
            cursor.execute(
                "SELECT 1 FROM enrollments WHERE user_id=%s AND course_id=%s "
                "AND enrollment_status='active'", (user['id'], session['course_id'])
            )
            if not cursor.fetchone():
                return {'status': 'NOT_ENROLLED', 'name': user['name']}
            cursor.execute(
                'SELECT status FROM attendance_records WHERE session_id=%s AND user_id=%s FOR UPDATE',
                (session_id, user['id'])
            )
            previous = cursor.fetchone()
            if previous and previous['status'] in {'present', 'late', 'excused'}:
                return {'status': 'ALREADY_MARKED', 'name': user['name'], 'attendance': previous['status']}
            threshold = session['starts_at'] + timedelta(minutes=session['late_after_minutes'])
            attendance_status = 'late' if now > threshold else 'present'
            cursor.execute('INSERT INTO attendance_history(session_id,user_id,previous_status,new_status,source,reason) VALUES(%s,%s,%s,%s,\'nfc\',\'Órai NFC-beolvasás\')',(session_id,user['id'],previous['status'] if previous else None,attendance_status))
            cursor.execute(
                'INSERT INTO attendance_records(session_id,user_id,status,marked_at,method) '
                'VALUES(%s,%s,%s,%s,\'nfc\') ON DUPLICATE KEY UPDATE '
                'status=VALUES(status),marked_at=VALUES(marked_at),method=VALUES(method),'
                'marked_by=NULL,note=NULL',
                (session_id,user['id'],attendance_status,now)
            )
            return {'status': attendance_status.upper(), 'name': user['name'],
                    'user_id': user['id'], 'session_id': session_id, 'marked_at': now}

    def record_active_nfc(self,card_id):
        card_id=(card_id or '').strip().upper()
        if not card_id:
            return {'status':'INVALID_CARD'}
        now=self.clock()
        with self.db.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM users WHERE card_id=%s AND active=1 AND role='student' AND deleted_at IS NULL",
                (card_id,)
            )
            user=cursor.fetchone()
            if not user:
                return {'status':'UNKNOWN_CARD'}
            cursor.execute(
                "SELECT s.id,e.user_id IS NOT NULL enrolled FROM course_sessions s "
                "LEFT JOIN enrollments e ON e.course_id=s.course_id AND e.user_id=%s "
                "AND e.enrollment_status='active' WHERE s.status IN ('planned','open') "
                "AND s.starts_at<=%s AND s.ends_at>%s ORDER BY s.starts_at,s.id",
                (user['id'],now,now)
            )
            sessions=cursor.fetchall()
        if not sessions:
            return {'status':'NO_ACTIVE_SESSION'}
        eligible=[row for row in sessions if row['enrolled']]
        if len(eligible)>1:
            return {'status':'AMBIGUOUS_SESSION'}
        if not eligible:
            return {'status':'NOT_ENROLLED'} if len(sessions)==1 else {'status':'AMBIGUOUS_SESSION'}
        return self.record_nfc(eligible[0]['id'],card_id)

    def attendance_summary(self, session_id):
        session = self.get_session(session_id)
        if not session:
            raise ValueError('Az alkalom nem található.')
        if session['status'] in {'planned', 'open'}:
            query = (
                "SELECT COUNT(*) enrolled,SUM(a.status='present') present_count,"
                "SUM(a.status='late') late_count,SUM(a.status='absent') absent_count,"
                "SUM(a.status='excused') excused_count FROM attendance_records a "
                "JOIN enrollments e ON e.course_id=%s AND e.user_id=a.user_id "
                "AND e.enrollment_status='active' WHERE a.session_id=%s"
            )
            params = (session['course_id'], session_id)
        else:
            query = (
                "SELECT COUNT(*) enrolled,SUM(a.status='present') present_count,"
                "SUM(a.status='late') late_count,SUM(a.status='absent') absent_count,"
                "SUM(a.status='excused') excused_count FROM attendance_records a "
                "WHERE a.session_id=%s"
            )
            params = (session_id,)
        with self.db.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    @staticmethod
    def _as_datetime(value):
        if isinstance(value, datetime):
            return value
        try:
            from zoneinfo import ZoneInfo
            parsed=datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            if parsed.tzinfo is not None:
                parsed=parsed.astimezone(ZoneInfo('Europe/Budapest')).replace(tzinfo=None)
            return parsed
        except (ValueError, TypeError):
            raise ValueError('A dátumot ISO 8601 formában add meg.')

    def create_series(self, course_id, first_start, duration_minutes, weeks,
                      room=None, title=None, late_after_minutes=10, created_by=None):
        first_start=self._as_datetime(first_start)
        duration_minutes=int(duration_minutes)
        weeks=int(weeks)
        if duration_minutes<15 or duration_minutes>360:
            raise ValueError('Az alkalom hossza 15 és 360 perc közé essen.')
        if weeks<1 or weeks>20:
            raise ValueError('Egy sorozat 1 és 20 hét közötti legyen.')
        if late_after_minutes<0 or late_after_minutes>180:
            raise ValueError('A késési türelmi idő 0 és 180 perc közé essen.')
        room=(room or '').strip() or None
        title=(title or '').strip() or None
        inserted=[]
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('SELECT id FROM courses WHERE id=%s AND active=1 FOR UPDATE',(course_id,))
            if not cursor.fetchone():
                raise ValueError('Az aktív kurzus nem található.')
            for week in range(weeks):
                starts=first_start+timedelta(days=7*week)
                ends=starts+timedelta(minutes=duration_minutes)
                cursor.execute(
                    "SELECT id FROM course_sessions WHERE status<>'cancelled' "
                    "AND starts_at < %s AND ends_at > %s "
                    "AND (course_id=%s OR (%s IS NOT NULL AND room=%s)) LIMIT 1",
                    (ends,starts,course_id,room,room),
                )
                conflict=cursor.fetchone()
                if conflict:
                    raise ValueError(f'A sorozat {week+1}. alkalma időpont- vagy teremütközést okoz.')
                cursor.execute(
                    'INSERT INTO course_sessions(course_id,title,starts_at,ends_at,room,'
                    'late_after_minutes,created_by) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                    (course_id,title,starts,ends,room,late_after_minutes,created_by),
                )
                session_id=cursor.lastrowid
                cursor.execute(
                    "INSERT INTO attendance_records(session_id,user_id,status,method) "
                    "SELECT %s,e.user_id,'absent','manual' FROM enrollments e "
                    "JOIN users u ON u.id=e.user_id WHERE e.course_id=%s "
                    "AND e.enrollment_status='active' AND u.active=1",
                    (session_id,course_id),
                )
                inserted.append(session_id)
        return inserted

    def mark_bulk(self, session_id, changes, actor_id, note=None):
        if not isinstance(changes,list) or not changes:
            raise ValueError('Legalább egy jelenléti módosítás szükséges.')
        if len(changes)>500:
            raise ValueError('Egy csoportos mentés legfeljebb 500 hallgatót érinthet.')
        session=self.get_session(session_id)
        if not session or session['status'] in {'closed','cancelled'}:
            raise ValueError('A hiányzó, lezárt vagy törölt alkalom nem módosítható.')
        normalized=[]
        for item in changes:
            user_id=int(item.get('user_id'))
            status=item.get('status')
            if status not in ATTENDANCE_STATES:
                raise ValueError(f'Érvénytelen jelenléti állapot: {status}')
            normalized.append((user_id,status))
        if len({user_id for user_id,_ in normalized})!=len(normalized):
            raise ValueError('Egy hallgató csak egyszer szerepelhet a csoportos mentésben.')
        ids=[user_id for user_id,_ in normalized]
        placeholders=','.join(['%s']*len(ids))
        with self.db.cursor(commit=True) as cursor:
            cursor.execute(
                f"SELECT user_id FROM enrollments WHERE course_id=%s AND enrollment_status='active' "
                f'AND user_id IN ({placeholders})', (session['course_id'],*ids)
            )
            eligible={row['user_id'] for row in cursor.fetchall()}
            if eligible!=set(ids):
                raise ValueError('A listában nem aktív kurzusfelvett hallgató szerepel.')
            now=self.clock()
            for user_id,status in normalized:
                marked_at=now if status in {'present','late'} else None
                cursor.execute('SELECT status FROM attendance_records WHERE session_id=%s AND user_id=%s FOR UPDATE',(session_id,user_id))
                previous=cursor.fetchone()
                cursor.execute('INSERT INTO attendance_history(session_id,user_id,actor_id,previous_status,new_status,source,reason) VALUES(%s,%s,%s,%s,%s,\'manual\',%s)',(session_id,user_id,actor_id,previous['status'] if previous else None,status,note))
                cursor.execute(
                    'INSERT INTO attendance_records(session_id,user_id,status,marked_at,marked_by,method,note) '
                    "VALUES(%s,%s,%s,%s,%s,'manual',%s) ON DUPLICATE KEY UPDATE "
                    'status=VALUES(status),marked_at=VALUES(marked_at),marked_by=VALUES(marked_by),'
                    'method=VALUES(method),note=VALUES(note)',
                    (session_id,user_id,status,marked_at,actor_id,(note or '')[:500] or None),
                )
        return {'session_id':session_id,'updated':len(normalized),'marked_by':actor_id}

    def attendance_history(self, session_id, user_id, limit=100):
        with self.db.cursor() as cursor:
            cursor.execute(
                'SELECT h.id,h.previous_status,h.new_status,h.source,h.reason,h.changed_at,'
                'actor.name actor_name FROM attendance_history h '
                'LEFT JOIN users actor ON actor.id=h.actor_id '
                'WHERE h.session_id=%s AND h.user_id=%s ORDER BY h.changed_at DESC,h.id DESC LIMIT %s',
                (session_id,user_id,max(1,min(int(limit),200)))
            )
            return cursor.fetchall()






