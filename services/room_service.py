from datetime import datetime
from database.connection import Database

class RoomService:
    def __init__(self,db=None):
        self.db=db or Database()

    def list_rooms(self,active_after=None,active_before=None):
        query=("SELECT DISTINCT TRIM(room) room FROM course_sessions "
               "WHERE room IS NOT NULL AND TRIM(room)<>'' AND status<>'cancelled'")
        params=[]
        if active_after:
            query+=' AND ends_at>%s';params.append(active_after)
        if active_before:
            query+=' AND starts_at<%s';params.append(active_before)
        query+=' ORDER BY room'
        with self.db.cursor() as cursor:
            cursor.execute(query,tuple(params))
            return [row['room'] for row in cursor.fetchall()]

    def availability(self,room,starts_at,ends_at,exclude_session_id=None):
        room=(room or '').strip()
        if not room:
            raise ValueError('A terem megadása kötelező.')
        if starts_at>=ends_at:
            raise ValueError('A befejezési időpontnak a kezdés után kell lennie.')
        query=("SELECT s.id,s.course_id,c.code,c.name,s.title,s.starts_at,s.ends_at,s.status "
               'FROM course_sessions s JOIN courses c ON c.id=s.course_id '
               "WHERE s.room=%s AND s.status<>'cancelled' AND s.starts_at<%s AND s.ends_at>%s")
        params=[room,ends_at,starts_at]
        if exclude_session_id:
            query+=' AND s.id<>%s';params.append(exclude_session_id)
        query+=' ORDER BY s.starts_at'
        with self.db.cursor() as cursor:
            cursor.execute(query,tuple(params))
            conflicts=cursor.fetchall()
        return {'room':room,'available':not conflicts,'conflicts':conflicts}

    def calendar(self,from_time,to_time,teacher_id=None):
        if isinstance(from_time,str):
            from_time=datetime.fromisoformat(from_time)
        if isinstance(to_time,str):
            to_time=datetime.fromisoformat(to_time)
        if from_time>=to_time:
            raise ValueError('A naptári intervallum hibás.')
        query=(
            "SELECT s.id,s.title,s.starts_at,s.ends_at,s.room,s.status,c.code,c.name "
            'FROM course_sessions s JOIN courses c ON c.id=s.course_id '
            "WHERE s.status<>'cancelled' AND s.starts_at<%s AND s.ends_at>%s"
        )
        params=[to_time,from_time]
        if teacher_id is not None:
            query+=' AND c.teacher_id=%s'
            params.append(teacher_id)
        query+=' ORDER BY s.starts_at,c.code'
        with self.db.cursor() as cursor:
            cursor.execute(
                query,tuple(params)
            )
            return cursor.fetchall()
