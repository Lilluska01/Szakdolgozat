from datetime import datetime, timezone
from pathlib import Path
from config.config import Config
from database.connection import Database

class SystemHealthService:
    def __init__(self,db=None):
        self.db=db or Database()

    def details(self):
        report={'checked_at':datetime.now(timezone.utc).isoformat(),'components':{}}
        started=datetime.now(timezone.utc)
        try:
            with self.db.cursor() as cursor:
                cursor.execute('SELECT VERSION() version,UTC_TIMESTAMP() database_time')
                database=cursor.fetchone()
            elapsed=(datetime.now(timezone.utc)-started).total_seconds()*1000
            report['components']['database']={'status':'ok','version':database['version'],
                                               'latency_ms':round(elapsed,2)}
        except Exception as exc:
            report['components']['database']={'status':'error','message':str(exc)[:180]}
        try:
            Config.LOG_DIR.mkdir(parents=True,exist_ok=True)
            log_file=Config.LOG_DIR/'attendance.log'
            writable=log_file.parent.exists()
            report['components']['logging']={'status':'ok' if writable else 'error',
                                             'directory':str(log_file.parent)}
        except OSError as exc:
            report['components']['logging']={'status':'error','message':str(exc)[:180]}
        try:
            from smartcard.System import readers
            connected=[str(reader) for reader in readers()]
            report['components']['nfc']={'status':'ok' if connected else 'unavailable',
                                         'reader_count':len(connected),'readers':connected}
        except Exception as exc:
            report['components']['nfc']={'status':'unavailable','message':str(exc)[:180]}
        report['status']='ok' if report['components']['database']['status']=='ok' else 'degraded'
        report['production_secret_configured']=Config.SECRET_KEY!='change-this-development-secret'
        return report
