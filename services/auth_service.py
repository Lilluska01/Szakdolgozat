import hashlib
from datetime import datetime, timedelta, timezone
import jwt
import bcrypt
from database.connection import Database
from config.config import Config

class AuthService:
    def __init__(self, db=None):
        self.db = db or Database()
        self.secret = Config.SECRET_KEY

    def hash_password(self, password):
        if not isinstance(password,str) or len(password) < 8:
            raise ValueError('A jelszó legalább 8 karakter legyen.')
        if len(password.encode('utf-8')) > 72:
            raise ValueError('A jelszó legfeljebb 72 bájt lehet bcrypt használatakor.')
        return bcrypt.hashpw(password.encode('utf-8'),bcrypt.gensalt()).decode('ascii')

    def verify_password(self, password, hashed):
        if not isinstance(password,str) or not hashed:
            return False
        try:
            return bcrypt.checkpw(password.encode('utf-8'),hashed.encode('ascii'))
        except (ValueError, TypeError):
            return False

    def login(self, email, password):
        user = self._get_user(email)
        password_hash = (user or {}).get('password_hash')
        if not user or not user.get('active') or user.get('role') not in {'admin','teacher'} or not self.verify_password(password, password_hash):
            return None
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=Config.TOKEN_TTL_HOURS)
        payload = {'user_id': user['id'], 'role': user['role'], 'iat': now, 'exp': expires}
        token = jwt.encode(payload, self.secret, algorithm='HS256')
        digest = self._digest(token)
        with self.db.cursor(commit=True) as cursor:
            cursor.execute(
                'INSERT INTO api_tokens(user_id,token_hash,expires_at) VALUES(%s,%s,%s)',
                (user['id'],digest,expires.replace(tzinfo=None)),
            )
            cursor.execute('DELETE FROM api_tokens WHERE expires_at < UTC_TIMESTAMP()')
        return token

    def _get_user(self, email):
        with self.db.cursor() as cursor:
            cursor.execute('SELECT * FROM users WHERE email=%s', ((email or '').strip().lower(),))
            return cursor.fetchone()

    def _decode(self, token):
        if token and token.lower().startswith('bearer '):
            token = token[7:].strip()
        try:
            claims=jwt.decode(token,self.secret,algorithms=['HS256'])
            return token,claims
        except (jwt.InvalidTokenError,AttributeError,TypeError):
            return None,None

    def verify_token(self, token):
        identity=self.get_token_user(token)
        return identity.get('user_id') if identity else None

    def get_token_user(self, token):
        token,claims=self._decode(token)
        if not claims:
            return None
        digest=self._digest(token)
        with self.db.cursor() as cursor:
            cursor.execute(
                'SELECT u.id,u.name,u.email,u.role,u.active,t.expires_at '
                'FROM api_tokens t JOIN users u ON u.id=t.user_id '
                'WHERE t.token_hash=%s', (digest,)
            )
            user=cursor.fetchone()
        if not user or not user['active'] or user['expires_at'] <= datetime.utcnow():
            return None
        return {'user_id':user['id'],'name':user['name'],'email':user['email'],
                'role':user['role'],'token_id':digest}

    def revoke_token(self, token):
        token,claims=self._decode(token)
        if not claims:
            return False
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('DELETE FROM api_tokens WHERE token_hash=%s',(self._digest(token),))
            return cursor.rowcount>0

    @staticmethod
    def _digest(token):
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def change_password(self,user_id,current_password,new_password):
        if not isinstance(new_password,str) or len(new_password)<8:
            raise ValueError('Az új jelszó legalább 8 karakter legyen.')
        if len(new_password.encode('utf-8'))>72:
            raise ValueError('Az új jelszó legfeljebb 72 bájt lehet.')
        with self.db.cursor() as cursor:
            cursor.execute('SELECT password_hash FROM users WHERE id=%s AND active=1',(user_id,))
            user=cursor.fetchone()
        if not user or not self.verify_password(current_password,user.get('password_hash')):
            raise ValueError('A jelenlegi jelszó hibás.')
        password_hash=self.hash_password(new_password)
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('UPDATE users SET password_hash=%s WHERE id=%s',(password_hash,user_id))
            cursor.execute('DELETE FROM api_tokens WHERE user_id=%s',(user_id,))
        return True
