import re
from database.connection import Database

class CourseService:
    def __init__(self,db=None):
        self.db=db or Database()

    def create_course(self,code,name,teacher_id=None,description=None):
        code=(code or '').strip().upper();name=(name or '').strip()
        description=(description or '').strip() or None
        if not re.fullmatch(r'[A-Z0-9_-]{2,32}',code):
            raise ValueError('A kurzuskód 2–32 betűt, számot, kötőjelet vagy aláhúzást tartalmazhat.')
        if not name or len(name)>160:
            raise ValueError('A kurzus neve kötelező, legfeljebb 160 karakter lehet.')
        if description and len(description)>4000:
            raise ValueError('A kurzusleírás legfeljebb 4 000 karakter lehet.')
        with self.db.cursor(commit=True) as cursor:
            if teacher_id is not None:
                cursor.execute("SELECT id FROM users WHERE id=%s AND role IN ('teacher','admin') AND active=1",(teacher_id,))
                if not cursor.fetchone():
                    raise ValueError('A megadott aktív oktató nem található.')
            cursor.execute(
                'INSERT INTO courses(code,name,description,teacher_id,active) VALUES(%s,%s,%s,%s,1)',
                (code,name,description,teacher_id)
            )
            return cursor.lastrowid

    def update_course(self,course_id,*,code=None,name=None,description=None,teacher_id=None,teacher_id_supplied=False):
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('SELECT id,code,name,description,teacher_id FROM courses WHERE id=%s FOR UPDATE',(course_id,))
            current=cursor.fetchone()
            if not current:
                raise ValueError('A kurzus nem található.')
            new_code=current['code'] if code is None else code.strip().upper()
            new_name=current['name'] if name is None else name.strip()
            new_description=current['description'] if description is None else (description.strip() or None)
            new_teacher=teacher_id if teacher_id_supplied else current['teacher_id']
            if not re.fullmatch(r'[A-Z0-9_-]{2,32}',new_code):
                raise ValueError('A kurzuskód 2–32 betűt, számot, kötőjelet vagy aláhúzást tartalmazhat.')
            if not new_name or len(new_name)>160:
                raise ValueError('A kurzus neve kötelező, legfeljebb 160 karakter lehet.')
            if new_description and len(new_description)>4000:
                raise ValueError('A kurzusleírás túl hosszú.')
            if new_teacher is not None:
                cursor.execute("SELECT id FROM users WHERE id=%s AND role IN ('teacher','admin') AND active=1",(new_teacher,))
                if not cursor.fetchone():
                    raise ValueError('A megadott aktív oktató nem található.')
            cursor.execute('UPDATE courses SET code=%s,name=%s,description=%s,teacher_id=%s WHERE id=%s',
                           (new_code,new_name,new_description,new_teacher,course_id))
        return self.get_course(course_id)

    def get_course(self,course_id):
        with self.db.cursor() as cursor:
            cursor.execute(
                'SELECT c.id,c.code,c.name,c.description,c.teacher_id,u.name teacher_name,c.active '
                'FROM courses c LEFT JOIN users u ON u.id=c.teacher_id WHERE c.id=%s',(course_id,)
            )
            return cursor.fetchone()

    def list_courses(self,active_only=True,*,search=None,teacher_id=None,limit=500,offset=0):
        limit=max(1,min(int(limit),1000));offset=max(0,int(offset))
        query=(
            'SELECT c.id,c.code,c.name,c.description,c.teacher_id,u.name teacher_name,c.active,'
            "SUM(e.enrollment_status='active') student_count "
            'FROM courses c LEFT JOIN users u ON u.id=c.teacher_id '
            'LEFT JOIN enrollments e ON e.course_id=c.id WHERE 1=1'
        )
        params=[]
        if active_only:
            query+=' AND c.active=1'
        if teacher_id is not None:
            query+=' AND c.teacher_id=%s';params.append(teacher_id)
        if search:
            query+=' AND (c.code LIKE %s OR c.name LIKE %s)'
            pattern='%'+search.strip()[:100]+'%';params.extend((pattern,pattern))
        query+=(
            ' GROUP BY c.id,c.code,c.name,c.description,c.teacher_id,u.name,c.active '
            'ORDER BY c.code LIMIT %s OFFSET %s'
        )
        params.extend((limit,offset))
        with self.db.cursor() as cursor:
            cursor.execute(query,tuple(params))
            return cursor.fetchall()

    def enroll(self,course_id,user_id):
        with self.db.cursor(commit=True) as cursor:
            self._validate_enrollment(cursor,course_id,user_id)
            cursor.execute("INSERT IGNORE INTO enrollments(user_id,course_id,enrollment_status) VALUES(%s,%s,'active')",
                           (user_id,course_id))
            created=cursor.rowcount>0
            if created:
                self._create_upcoming_marks(cursor,course_id,user_id)
            else:
                cursor.execute("UPDATE enrollments SET enrollment_status='active' WHERE user_id=%s AND course_id=%s",
                               (user_id,course_id))
        return created

    def enroll_many(self,course_id,user_ids):
        if not isinstance(user_ids,list) or not user_ids or len(user_ids)>500:
            raise ValueError('1–500 hallgatói azonosító szükséges.')
        ids=list(dict.fromkeys(int(value) for value in user_ids))
        created=[];existing=[];missing=[]
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('SELECT id FROM courses WHERE id=%s AND active=1 FOR UPDATE',(course_id,))
            if not cursor.fetchone():
                raise ValueError('Az aktív kurzus nem található.')
            placeholders=','.join(['%s']*len(ids))
            cursor.execute(f"SELECT id FROM users WHERE role='student' AND active=1 AND id IN ({placeholders})",tuple(ids))
            valid={row['id'] for row in cursor.fetchall()}
            missing=sorted(set(ids)-valid)
            for user_id in ids:
                if user_id not in valid:
                    continue
                cursor.execute("INSERT IGNORE INTO enrollments(user_id,course_id,enrollment_status) VALUES(%s,%s,'active')",
                               (user_id,course_id))
                if cursor.rowcount:
                    created.append(user_id)
                    self._create_upcoming_marks(cursor,course_id,user_id)
                else:
                    existing.append(user_id)
                    cursor.execute("UPDATE enrollments SET enrollment_status='active' WHERE user_id=%s AND course_id=%s",
                                   (user_id,course_id))
        return {'created':created,'already_enrolled':existing,'not_found_or_invalid':missing}

    def remove_enrollment(self,course_id,user_id):
        with self.db.cursor(commit=True) as cursor:
            cursor.execute("UPDATE enrollments SET enrollment_status='withdrawn' WHERE course_id=%s AND user_id=%s AND enrollment_status='active'",
                           (course_id,user_id))
            return cursor.rowcount>0

    def list_students(self,course_id,*,search=None,limit=500,offset=0):
        limit=max(1,min(int(limit),1000));offset=max(0,int(offset))
        query=(
            "SELECT u.id,u.name,u.neptun,u.email,u.card_id,e.enrolled_at,e.enrollment_status "
            "FROM enrollments e JOIN users u ON u.id=e.user_id "
            "WHERE e.course_id=%s AND e.enrollment_status='active'"
        )
        params=[course_id]
        if search:
            query+=' AND (u.name LIKE %s OR u.neptun LIKE %s OR u.email LIKE %s)'
            pattern='%'+search.strip()[:100]+'%';params.extend((pattern,pattern,pattern))
        query+=' ORDER BY u.name LIMIT %s OFFSET %s';params.extend((limit,offset))
        with self.db.cursor() as cursor:
            cursor.execute(query,tuple(params))
            return cursor.fetchall()

    def set_active(self,course_id,active):
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('UPDATE courses SET active=%s WHERE id=%s',(bool(active),course_id))
            if not cursor.rowcount:
                raise ValueError('A kurzus nem található.')
            return bool(active)

    @staticmethod
    def _validate_enrollment(cursor,course_id,user_id):
        cursor.execute('SELECT id FROM courses WHERE id=%s AND active=1 FOR UPDATE',(course_id,))
        if not cursor.fetchone():
            raise ValueError('Az aktív kurzus nem található.')
        cursor.execute("SELECT id FROM users WHERE id=%s AND role='student' AND active=1 FOR UPDATE",(user_id,))
        if not cursor.fetchone():
            raise ValueError('Az aktív hallgató nem található.')

    @staticmethod
    def _create_upcoming_marks(cursor,course_id,user_id):
        cursor.execute(
            "INSERT IGNORE INTO attendance_records(session_id,user_id,status,method) "
            "SELECT id,%s,'absent','manual' FROM course_sessions "
            "WHERE course_id=%s AND status IN ('planned','open')",
            (user_id,course_id)
        )
