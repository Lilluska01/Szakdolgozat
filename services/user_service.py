import re
from database.connection import Database
from models.user import User

class UserService:
    VALID_ROLES={'student','teacher','admin'}

    def __init__(self,db=None):
        self.db=db or Database()

    @staticmethod
    def _execute_user_query(cursor,query,params):
        try:
            cursor.execute(query,params)
        except Exception as exc:
            if getattr(exc,'errno',None)!=1054 or 'created_at' not in str(exc):
                raise
            fallback=query.replace(',created_at FROM users', ',NULL AS created_at FROM users', 1)
            if fallback==query:
                raise
            cursor.execute(fallback,params)

    def get_user_by_card(self,card_id):
        card=(card_id or '').strip().upper()
        if not card:
            return None
        with self.db.cursor() as cursor:
            cursor.execute('SELECT * FROM users WHERE card_id=%s',(card,))
            row=cursor.fetchone()
        return User(**row) if row else None

    def get_user(self,user_id):
        with self.db.cursor() as cursor:
            self._execute_user_query(cursor,'SELECT id,name,email,neptun,card_id,role,active,is_inside,last_seen,created_at FROM users WHERE id=%s',(user_id,))
            return cursor.fetchone()

    def create_user(self,name,neptun=None,role='student',email=None,password=None):
        values=self._validate_profile(name,neptun,role,email)
        if role=='admin':
            raise ValueError('Adminisztrátori fiókot csak meglévő adminisztrátor állíthat be.')
        password_hash=None
        if role=='teacher':
            if not email or not password:
                raise ValueError('Oktatói fiókhoz e-mail-cím és jelszó szükséges.')
            from services.auth_service import AuthService
            password_hash=AuthService().hash_password(password)
        with self.db.cursor(commit=True) as cursor:
            cursor.execute(
                'INSERT INTO users(name,neptun,role,email,password_hash,active,is_inside) '
                'VALUES(%s,%s,%s,%s,%s,1,0)',
                (*values,password_hash)
            )
            return cursor.lastrowid

    def update_user(self,user_id,*,name=None,neptun=None,email=None,role=None):
        current=self.get_user(user_id)
        if not current:
            raise ValueError('A felhasználó nem található.')
        values=self._validate_profile(
            current['name'] if name is None else name,
            current['neptun'] if neptun is None else neptun,
            current['role'] if role is None else role,
            current['email'] if email is None else email,
        )
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('UPDATE users SET name=%s,neptun=%s,role=%s,email=%s WHERE id=%s',(*values,user_id))
            return self.get_user(user_id)

    def assign_card(self,user_id,card_id,actor_id=None):
        card=(card_id or '').strip().upper()
        if not card or len(card)>64 or not re.fullmatch(r'[A-Z0-9:-]+',card):
            raise ValueError('Érvényes kártyaazonosító szükséges.')
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('SELECT id,card_id,deleted_at FROM users WHERE id=%s FOR UPDATE',(user_id,))
            user=cursor.fetchone()
            if not user:
                raise ValueError('A felhasználó nem található.')
            if user['deleted_at']:
                raise ValueError('Az archivált felhasználóhoz nem rendelhető kártya.')
            cursor.execute('SELECT id FROM users WHERE card_id=%s AND id<>%s',(card,user_id))
            if cursor.fetchone():
                raise ValueError('Ez a kártya már egy másik felhasználóhoz tartozik.')
            cursor.execute(
                'INSERT INTO card_assignment_history(user_id,actor_id,old_card_id,new_card_id,action) '
                "VALUES(%s,%s,%s,%s,'assigned')",
                (user_id,actor_id,user['card_id'],card)
            )
            cursor.execute('UPDATE users SET card_id=%s WHERE id=%s',(card,user_id))

    def unassign_card(self,user_id,actor_id=None):
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('SELECT card_id FROM users WHERE id=%s FOR UPDATE',(user_id,))
            user=cursor.fetchone()
            if not user:
                raise ValueError('A felhasználó nem található.')
            if not user['card_id']:
                return False
            cursor.execute(
                'INSERT INTO card_assignment_history(user_id,actor_id,old_card_id,new_card_id,action) '
                "VALUES(%s,%s,%s,NULL,'unassigned')",(user_id,actor_id,user['card_id'])
            )
            cursor.execute('UPDATE users SET card_id=NULL WHERE id=%s',(user_id,))
            return True

    def delete_user(self,user_id,actor_id=None):
        from datetime import datetime
        now=datetime.now()
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('SELECT id,name,card_id,is_inside,role,deleted_at FROM users WHERE id=%s FOR UPDATE',(user_id,))
            user=cursor.fetchone()
            if not user:
                raise ValueError('A felhasználó nem található.')
            if user['role']=='admin':
                raise ValueError('Webes adminfiók nem törölhető a kártyakezelőből.')
            if user['deleted_at']:
                return {'id':user_id,'name':user['name'],'released_card':user['card_id'],'status':'archived'}
            if user['card_id']:
                cursor.execute(
                    'INSERT INTO card_assignment_history(user_id,actor_id,old_card_id,new_card_id,action) '
                    "VALUES(%s,%s,%s,NULL,'unassigned')",
                    (user_id,actor_id,user['card_id'])
                )
            if user['is_inside']:
                cursor.execute(
                    "INSERT INTO access_logs(user_id,card_id,action,timestamp) VALUES(%s,%s,'EXIT',%s)",
                    (user_id,user['card_id'] or 'ADMIN',now)
                )
            cursor.execute(
                'UPDATE users SET active=0,card_id=NULL,is_inside=0,last_seen=%s,deleted_at=%s WHERE id=%s',
                (now,now,user_id)
            )
            return {'id':user_id,'name':user['name'],'released_card':user['card_id'],'status':'archived'}

    def card_history(self,user_id,limit=100):
        with self.db.cursor() as cursor:
            cursor.execute(
                'SELECT h.id,h.old_card_id,h.new_card_id,h.action,h.changed_at,u.name actor_name '
                'FROM card_assignment_history h LEFT JOIN users u ON u.id=h.actor_id '
                'WHERE h.user_id=%s ORDER BY h.changed_at DESC LIMIT %s',
                (user_id,max(1,min(int(limit),200)))
            )
            return cursor.fetchall()

    def get_all_users(self,include_inactive=True,*,search=None,role=None,limit=500,offset=0,include_admin=True,include_archived=False):
        limit=max(1,min(int(limit),1000));offset=max(0,int(offset))
        query='SELECT id,name,email,neptun,card_id,role,active,is_inside,last_seen,created_at FROM users WHERE 1=1'
        params=[]
        if not include_inactive:
            query+=' AND active=1'
        if not include_admin:
            query+=" AND role<>'admin'"
        if not include_archived:
            query+=' AND deleted_at IS NULL'
        if role:
            if role not in self.VALID_ROLES:
                raise ValueError('Érvénytelen szerepkör.')
            query+=' AND role=%s';params.append(role)
        if search:
            query+=' AND (name LIKE %s OR neptun LIKE %s OR email LIKE %s OR card_id LIKE %s)'
            pattern='%'+search.strip()[:100]+'%';params.extend((pattern,pattern,pattern,pattern))
        query+=' ORDER BY name,id LIMIT %s OFFSET %s';params.extend((limit,offset))
        with self.db.cursor() as cursor:
            self._execute_user_query(cursor,query,tuple(params))
            return cursor.fetchall()

    def list_students_for_teacher(self,teacher_id,*,search=None,limit=500,offset=0):
        limit=max(1,min(int(limit),1000));offset=max(0,int(offset))
        query=(
            "SELECT DISTINCT u.id,u.name,u.email,u.neptun,u.card_id,u.role,u.active,"
            "u.is_inside,u.last_seen,u.created_at FROM users u "
            "JOIN enrollments e ON e.user_id=u.id AND e.enrollment_status='active' "
            'JOIN courses c ON c.id=e.course_id WHERE c.teacher_id=%s '
            "AND u.role='student' AND u.active=1 AND u.deleted_at IS NULL"
        )
        params=[teacher_id]
        if search:
            query+=' AND (u.name LIKE %s OR u.neptun LIKE %s OR u.card_id LIKE %s)'
            pattern='%'+search.strip()[:100]+'%';params.extend((pattern,pattern,pattern))
        query+=' ORDER BY u.name,u.id LIMIT %s OFFSET %s';params.extend((limit,offset))
        with self.db.cursor() as cursor:
            try:
                cursor.execute(query,tuple(params))
            except Exception as exc:
                if getattr(exc,'errno',None)!=1054 or 'created_at' not in str(exc):
                    raise
                cursor.execute(query.replace('u.created_at','NULL AS created_at'),tuple(params))
            return cursor.fetchall()

    def count_users(self,include_inactive=True,*,search=None,role=None,include_admin=True,include_archived=False):
        query='SELECT COUNT(*) total FROM users WHERE 1=1';params=[]
        if not include_inactive:
            query+=' AND active=1'
        if not include_admin:
            query+=" AND role<>'admin'"
        if not include_archived:
            query+=' AND deleted_at IS NULL'
        if role:
            if role not in self.VALID_ROLES:
                raise ValueError('Érvénytelen szerepkör.')
            query+=' AND role=%s';params.append(role)
        if search:
            query+=' AND (name LIKE %s OR neptun LIKE %s OR email LIKE %s OR card_id LIKE %s)'
            pattern='%'+search.strip()[:100]+'%';params.extend((pattern,pattern,pattern,pattern))
        with self.db.cursor() as cursor:
            cursor.execute(query,tuple(params))
            return cursor.fetchone()['total']

    def toggle_active(self,user_id):
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('UPDATE users SET active=NOT active WHERE id=%s AND deleted_at IS NULL',(user_id,))
            if not cursor.rowcount:
                raise ValueError('A felhasználó nem található.')
            cursor.execute('SELECT active FROM users WHERE id=%s',(user_id,))
            return bool(cursor.fetchone()['active'])

    def set_active(self,user_id,active):
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('UPDATE users SET active=%s WHERE id=%s AND deleted_at IS NULL',(bool(active),user_id))
            if not cursor.rowcount:
                raise ValueError('A felhasználó nem található.')
            return bool(active)

    def get_by_email(self,email):
        with self.db.cursor() as cursor:
            cursor.execute('SELECT * FROM users WHERE email=%s AND active=1',((email or '').strip().lower(),))
            return cursor.fetchone()

    @classmethod
    def _validate_profile(cls,name,neptun,role,email):
        name=(name or '').strip()
        neptun=(neptun or '').strip().upper() or None
        role=(role or 'student').strip().lower()
        email=(email or '').strip().lower() or None
        if not name or len(name)>160:
            raise ValueError('A név kötelező, legfeljebb 160 karakter lehet.')
        if neptun and not re.fullmatch(r'[A-Z0-9]{6}',neptun):
            raise ValueError('A Neptun-kód pontosan 6 betű vagy szám legyen.')
        if role not in cls.VALID_ROLES:
            raise ValueError('Érvénytelen felhasználói szerepkör.')
        if email and (len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)):
            raise ValueError('Érvénytelen e-mail-cím.')
        return name,neptun,role,email
