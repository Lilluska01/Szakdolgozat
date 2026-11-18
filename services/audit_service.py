from database.connection import Database

class AuditService:
    def __init__(self, db=None):
        self.db = db or Database()

    def record(self, actor_id, event_type, entity_type, entity_id, summary):
        event_type = (event_type or '').strip()[:48]
        entity_type = (entity_type or '').strip()[:48]
        summary = (summary or '').strip()[:500]
        if not event_type or not entity_type or not summary:
            raise ValueError('Az auditbejegyzés kötelező mezői hiányoznak.')
        with self.db.cursor(commit=True) as cursor:
            cursor.execute(
                'INSERT INTO audit_events(actor_id,event_type,entity_type,entity_id,summary) '
                'VALUES(%s,%s,%s,%s,%s)',
                (actor_id,event_type,entity_type,str(entity_id)[:64] if entity_id is not None else None,summary)
            )
            return cursor.lastrowid

    def search(self, *, actor_id=None, event_type=None, entity_type=None,
               from_time=None, to_time=None, limit=100, offset=0):
        query = (
            'SELECT a.id,a.actor_id,u.name actor_name,a.event_type,a.entity_type,'
            'a.entity_id,a.summary,a.created_at FROM audit_events a '
            'LEFT JOIN users u ON u.id=a.actor_id WHERE 1=1'
        )
        params = []
        for column, value in [('a.actor_id',actor_id),('a.event_type',event_type),('a.entity_type',entity_type)]:
            if value is not None:
                query += f' AND {column}=%s'; params.append(value)
        if from_time:
            query += ' AND a.created_at >= %s'; params.append(from_time)
        if to_time:
            query += ' AND a.created_at < %s'; params.append(to_time)
        query += ' ORDER BY a.created_at DESC,a.id DESC LIMIT %s OFFSET %s'
        params.extend((max(1,min(int(limit),500)),max(0,int(offset))))
        with self.db.cursor() as cursor:
            cursor.execute(query,tuple(params))
            return cursor.fetchall()
