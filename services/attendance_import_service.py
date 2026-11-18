import csv
import io
from services.session_service import ATTENDANCE_STATES
from services.session_service import SessionService

class AttendanceImportService:
    STATUS_ALIASES={
        'jelen':'present','jelen volt':'present','present':'present','p':'present',
        'kesett':'late','késett':'late','late':'late','l':'late',
        'hianyzott':'absent','hiányzott':'absent','absent':'absent','a':'absent',
        'igazolt':'excused','excused':'excused','e':'excused',
    }

    def __init__(self,db=None,session_service=None):
        from database.connection import Database
        self.db=db or Database()
        self.sessions=session_service or SessionService(self.db)

    def preview(self,session_id,content):
        try:
            text=content.decode('utf-8-sig')
        except (AttributeError,UnicodeDecodeError) as exc:
            raise ValueError('A jelenléti fájlnak UTF-8 kódolásúnak kell lennie.') from exc
        if len(content)>1_000_000:
            raise ValueError('A fájl mérete legfeljebb 1 MB lehet.')
        try:
            dialect=csv.Sniffer().sniff(text[:4096],delimiters=',;\t')
        except csv.Error:
            dialect=csv.excel
        reader=csv.DictReader(io.StringIO(text),dialect=dialect)
        if not reader.fieldnames:
            raise ValueError('A fájl fejlécsort igényel.')
        fields={self._key(name):name for name in reader.fieldnames}
        student_column=next((fields[k] for k in ('neptun','neptun kod','student id') if k in fields),None)
        status_column=next((fields[k] for k in ('status','allapot','jelenlet') if k in fields),None)
        if not student_column or not status_column:
            raise ValueError('Kötelező oszlopok: Neptun-kód és Állapot.')
        roster=self.sessions.get_roster(session_id)['students']
        by_neptun={str(row.get('neptun') or '').upper():row for row in roster if row.get('neptun')}
        output=[];errors=[];seen=set()
        for number,row in enumerate(reader,start=2):
            neptun=str(row.get(student_column) or '').strip().upper()
            raw_status=self._key(row.get(status_column))
            status=self.STATUS_ALIASES.get(raw_status)
            student=by_neptun.get(neptun)
            row_errors=[]
            if not student:
                row_errors.append('A Neptun-kód nem szerepel az alkalom névsorában.')
            if not status:
                row_errors.append('Ismeretlen jelenléti állapot.')
            if neptun in seen:
                row_errors.append('A Neptun-kód többször szerepel a fájlban.')
            seen.add(neptun)
            output.append({'row':number,'neptun':neptun,'name':student['name'] if student else None,
                           'user_id':student['user_id'] if student else None,
                           'status':status,'errors':row_errors})
            for issue in row_errors:
                errors.append({'row':number,'neptun':neptun,'message':issue})
        return {'session_id':session_id,'total_rows':len(output),
                'valid_rows':sum(not item['errors'] for item in output),
                'invalid_rows':sum(bool(item['errors']) for item in output),
                'errors':errors,'rows':output[:1000],
                'can_import':bool(output) and not errors}

    def commit(self,session_id,preview,actor_id,reason='CSV-import'):
        if preview.get('session_id')!=session_id or not preview.get('can_import'):
            raise ValueError('Csak hibamentes, ehhez az alkalomhoz tartozó előnézet tölthető be.')
        changes=[{'user_id':row['user_id'],'status':row['status']} for row in preview['rows']]
        result=self.sessions.mark_bulk(session_id,changes,actor_id,reason)
        result['imported_rows']=len(changes)
        return result

    @staticmethod
    def _key(value):
        import unicodedata
        normalized=unicodedata.normalize('NFKD',str(value or '').strip().lower())
        plain=''.join(char for char in normalized if not unicodedata.combining(char))
        return ' '.join(plain.replace('_',' ').replace('-',' ').split())
