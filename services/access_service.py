from datetime import datetime
from config.config import Config
from database.connection import Database

class AccessService:
    def __init__(self, db=None, cooldown_seconds=None):
        self.db = db or Database()
        self.cooldown_seconds = Config.ACCESS_COOLDOWN_SECONDS if cooldown_seconds is None else cooldown_seconds

    def record_scan(self, card_id, source='nfc'):
        card_id = (card_id or '').strip().upper()
        if not card_id:
            return {'status': 'INVALID_CARD'}
        now = datetime.now()
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('SELECT id,name,card_id,active,is_inside,last_seen FROM users WHERE card_id=%s FOR UPDATE', (card_id,))
            user = cursor.fetchone()
            if not user:
                return {'status': 'UNKNOWN_CARD', 'card_id': card_id}
            if not user['active']:
                return {'status': 'DENIED', 'name': user['name']}
            last_seen = user['last_seen']
            if last_seen and (now - last_seen).total_seconds() < self.cooldown_seconds:
                return {'status': 'COOLDOWN', 'name': user['name']}
            action = 'EXIT' if user['is_inside'] else 'ENTRY'
            cursor.execute('INSERT INTO access_logs(user_id,card_id,action,source) VALUES(%s,%s,%s,%s)', (user['id'], card_id, action, source[:24]))
            cursor.execute('UPDATE users SET is_inside=%s,last_seen=%s WHERE id=%s', (action == 'ENTRY', now, user['id']))
            return {'status': action, 'user_id': user['id'], 'name': user['name'], 'timestamp': now}

    def log_access(self, user):
        result = self.record_scan(user.card_id)
        return result.get('status', 'ERROR')

    def get_currently_inside(self):
        with self.db.cursor() as cursor:
            cursor.execute('SELECT id,name,neptun,card_id,last_seen FROM users WHERE active=1 AND is_inside=1 ORDER BY name')
            return cursor.fetchall()

    def get_last_logs(self, limit=50, from_time=None, to_time=None):
        limit = max(1, min(int(limit), 500))
        query = 'SELECT a.id,a.user_id,u.name,u.neptun,a.card_id,a.action,a.source,a.timestamp FROM access_logs a JOIN users u ON u.id=a.user_id WHERE 1=1'
        params = []
        if from_time:
            query += ' AND a.timestamp >= %s'; params.append(from_time)
        if to_time:
            query += ' AND a.timestamp < %s'; params.append(to_time)
        query += ' ORDER BY a.timestamp DESC,a.id DESC LIMIT %s'; params.append(limit)
        with self.db.cursor() as cursor:
            cursor.execute(query, tuple(params))
            return cursor.fetchall()

    def get_summary(self):
        with self.db.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) total_users,SUM(active=1) active_users,SUM(active=1 AND is_inside=1) inside_now FROM users')
            summary = cursor.fetchone() or {}
            midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cursor.execute('SELECT COUNT(*) scans_today FROM access_logs WHERE timestamp >= %s', (midnight,))
            summary.update(cursor.fetchone() or {})
            return summary
    def force_exit(self,user_id,actor_id,reason):
        reason=(reason or '').strip()[:500]
        if not reason:
            raise ValueError('A kézi kijelentkeztetés indoklása kötelező.')
        now=datetime.now()
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('SELECT id,name,card_id,is_inside FROM users WHERE id=%s FOR UPDATE',(user_id,))
            user=cursor.fetchone()
            if not user:
                raise ValueError('A felhasználó nem található.')
            if not user['is_inside']:
                return {'status':'already_out','user_id':user_id,'name':user['name']}
            cursor.execute(
                "INSERT INTO access_logs(user_id,card_id,action,source,timestamp) "
                "VALUES(%s,%s,'EXIT','admin',%s)",
                (user_id,user['card_id'] or 'ADMIN',now)
            )
            log_id=cursor.lastrowid
            cursor.execute('UPDATE users SET is_inside=0,last_seen=%s WHERE id=%s',(now,user_id))
            cursor.execute(
                'INSERT INTO audit_events(actor_id,event_type,entity_type,entity_id,summary) '
                "VALUES(%s,'forced_exit','user',%s,%s)",
                (actor_id,str(user_id),f'Kézi kiléptetés: {reason}')
            )
        return {'status':'EXIT','user_id':user_id,'name':user['name'],
                'access_log_id':log_id,'timestamp':now,'reason':reason}

    def list_logs(self,*,search=None,action=None,user_id=None,from_time=None,to_time=None,
                  limit=100,offset=0):
        limit=max(1,min(int(limit),1000));offset=max(0,int(offset))
        if action and action not in {'ENTRY','EXIT'}:
            raise ValueError('Az eseménytípus ENTRY vagy EXIT legyen.')
        query=(
            'SELECT a.id,a.user_id,u.name,u.neptun,a.card_id,a.action,a.source,a.timestamp '
            'FROM access_logs a JOIN users u ON u.id=a.user_id WHERE 1=1'
        )
        params=[]
        if search:
            query+=' AND (u.name LIKE %s OR u.neptun LIKE %s OR a.card_id LIKE %s)'
            pattern='%'+search.strip()[:100]+'%';params.extend((pattern,pattern,pattern))
        if action:
            query+=' AND a.action=%s';params.append(action)
        if user_id is not None:
            query+=' AND a.user_id=%s';params.append(user_id)
        if from_time:
            query+=' AND a.timestamp >= %s';params.append(from_time)
        if to_time:
            query+=' AND a.timestamp < %s';params.append(to_time)
        query+=' ORDER BY a.timestamp DESC,a.id DESC LIMIT %s OFFSET %s'
        params.extend((limit,offset))
        with self.db.cursor() as cursor:
            cursor.execute(query,tuple(params))
            return cursor.fetchall()
    def daily_presence_report(self,day):
        from datetime import date as date_type,time
        if isinstance(day,str):
            try:
                day=date_type.fromisoformat(day)
            except ValueError as exc:
                raise ValueError('A dátum YYYY-MM-DD formátumú legyen.') from exc
        if isinstance(day,datetime):
            day=day.date()
        if not isinstance(day,date_type):
            raise ValueError('A jelentés dátuma hibás.')
        starts=datetime.combine(day,time.min)
        ends=starts+__import__('datetime').timedelta(days=1)
        with self.db.cursor() as cursor:
            cursor.execute(
                'SELECT a.id,a.user_id,a.action,a.timestamp FROM access_logs a '
                'WHERE a.timestamp >= %s AND a.timestamp < %s '
                'UNION ALL '
                'SELECT p.id,p.user_id,p.action,p.timestamp FROM access_logs p '
                'WHERE p.id=(SELECT x.id FROM access_logs x WHERE x.user_id=p.user_id '
                'AND x.timestamp < %s ORDER BY x.timestamp DESC,x.id DESC LIMIT 1) '
                'ORDER BY user_id,timestamp,id',
                (starts,ends,starts)
            )
            events=cursor.fetchall()
            cursor.execute('SELECT id,name,neptun,is_inside FROM users WHERE active=1')
            users=cursor.fetchall()
        grouped={}
        for event in events:
            grouped.setdefault(event['user_id'],[]).append(event)
        output=[]
        for user in users:
            inside=False;entry_at=None;seconds=0;seen_today=False;unpaired=0
            for event in grouped.get(user['id'],[]):
                at=event['timestamp']
                if at < starts:
                    inside=event['action']=='ENTRY'
                    entry_at=starts if inside else None
                    continue
                seen_today=True
                if event['action']=='ENTRY':
                    if not inside:
                        inside=True;entry_at=at
                    else:
                        unpaired+=1
                elif inside:
                    seconds+=max(0,int((at-entry_at).total_seconds()))
                    inside=False;entry_at=None
                else:
                    unpaired+=1
            if inside and entry_at:
                seconds+=max(0,int((ends-entry_at).total_seconds()))
            if seconds or seen_today or user['is_inside']:
                output.append({'user_id':user['id'],'name':user['name'],'neptun':user['neptun'],
                    'inside_seconds':seconds,'inside_minutes':round(seconds/60,1),
                    'still_inside':inside,'estimated_start':bool(inside and not seen_today),
                    'unpaired_events':unpaired})
        output.sort(key=lambda item:(-item['inside_seconds'],item['name']))
        return {'date':day.isoformat(),'users':output,
                'total_people':len(output),'total_inside_minutes':sum(row['inside_minutes'] for row in output)}
