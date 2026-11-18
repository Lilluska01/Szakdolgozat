import csv
import hashlib
import io
import re
import unicodedata
from pathlib import PurePath
from openpyxl import load_workbook
from database.connection import Database

MAX_IMPORT_BYTES = 1_500_000
MAX_IMPORT_ROWS = 5_000

class ImportValidationError(ValueError):
    pass

class StudentImportService:
    REQUIRED_COLUMNS = {'name', 'neptun'}
    HEADER_ALIASES = {
        'name': {'name','nev','hallgato','hallgato neve','student name'},
        'neptun': {'neptun','neptun kod','neptun code','student id'},
        'email': {'email','e mail','email cim','email address'},
    }

    def __init__(self, db=None):
        self.db = db or Database()

    def preview(self, file_name, content):
        file_name = self._validate_file(file_name, content)
        rows = self._read_rows(file_name, content)
        if len(rows) > MAX_IMPORT_ROWS:
            raise ImportValidationError(f'Egy import legfeljebb {MAX_IMPORT_ROWS} adatsort tartalmazhat.')
        normalized = []
        errors = []
        for number, row in enumerate(rows, start=2):
            student = self._normalize_row(row)
            row_errors = self._validate_student(student)
            if row_errors:
                errors.extend({'row': number, 'field': field, 'message': message}
                              for field, message in row_errors)
            normalized.append({'row': number, 'student': student, 'errors': row_errors})
        self._mark_repeated_values(normalized, errors)
        self._mark_existing_records(normalized, errors)
        error_rows = {item['row'] for item in errors}
        valid_count = sum(1 for item in normalized if item['row'] not in error_rows)
        return {
            'file_name': file_name,
            'sha256': hashlib.sha256(content).hexdigest(),
            'total_rows': len(normalized),
            'valid_rows': valid_count,
            'invalid_rows': len(error_rows),
            'errors': errors[:500],
            'sample': [item['student'] for item in normalized[:25]],
            'can_import': bool(normalized) and not errors,
        }

    def import_file(self, file_name, content, actor_id):
        file_name=self._validate_file(file_name,content)
        digest=hashlib.sha256(content).hexdigest()
        with self.db.cursor() as cursor:
            cursor.execute('SELECT id,inserted_rows FROM import_batches WHERE file_sha256=%s',(digest,))
            previous=cursor.fetchone()
        if previous:
            return {'status':'already_imported','batch_id':previous['id'],
                    'inserted_rows':previous['inserted_rows'],'sha256':digest}
        preview = self.preview(file_name, content)
        if not preview['total_rows']:
            raise ImportValidationError('A fájl nem tartalmaz importálható adatsort.')
        if preview['errors']:
            raise ImportValidationError({'message': 'Az import nem indítható hibás vagy duplikált sorokkal.',
                                         'preview': preview})
        students = [item['student'] for item in self._read_normalized(preview['file_name'], content)]
        digest = preview['sha256']
        with self.db.cursor(commit=True) as cursor:
            cursor.execute('SELECT id,inserted_rows FROM import_batches WHERE file_sha256=%s', (digest,))
            previous = cursor.fetchone()
            if previous:
                return {'status': 'already_imported', 'batch_id': previous['id'],
                        'inserted_rows': previous['inserted_rows'], 'sha256': digest}
            inserted = 0
            for student in students:
                cursor.execute(
                    "INSERT INTO users(name,neptun,email,role,active,is_inside) "
                    "VALUES(%s,%s,%s,'student',1,0)",
                    (student['name'],student['neptun'],student.get('email')),
                )
                inserted += 1
            cursor.execute(
                'INSERT INTO import_batches(actor_id,file_name,file_sha256,total_rows,inserted_rows,skipped_rows) '
                'VALUES(%s,%s,%s,%s,%s,0)',
                (actor_id,preview['file_name'][:255],digest,len(students),inserted),
            )
            batch_id = cursor.lastrowid
            cursor.execute(
                'INSERT INTO audit_events(actor_id,event_type,entity_type,entity_id,summary) '
                "VALUES(%s,'students_imported','import_batch',%s,%s)",
                (actor_id,str(batch_id),f'{inserted} hallgató importálva a {preview["file_name"]} fájlból.'),
            )
        return {'status': 'imported', 'batch_id': batch_id, 'inserted_rows': inserted,
                'skipped_rows': 0, 'sha256': digest}

    def history(self, limit=50, offset=0):
        limit=max(1,min(int(limit),200)); offset=max(0,int(offset))
        with self.db.cursor() as cursor:
            cursor.execute(
                'SELECT b.id,b.file_name,b.file_sha256,b.total_rows,b.inserted_rows,'
                'b.skipped_rows,b.created_at,u.name actor_name FROM import_batches b '
                'LEFT JOIN users u ON u.id=b.actor_id ORDER BY b.created_at DESC,b.id DESC '
                'LIMIT %s OFFSET %s', (limit,offset)
            )
            return cursor.fetchall()

    def _read_normalized(self, file_name, content):
        return [{'row': i, 'student': self._normalize_row(row)}
                for i,row in enumerate(self._read_rows(file_name,content),start=2)]

    @staticmethod
    def _validate_file(file_name, content):
        name = PurePath(str(file_name or '')).name
        if not name or PurePath(name).suffix.lower() not in {'.csv','.xlsx'}:
            raise ImportValidationError('Csak CSV vagy XLSX fájl tölthető fel.')
        if not isinstance(content,bytes) or not content:
            raise ImportValidationError('A feltöltött fájl üres.')
        if len(content) > MAX_IMPORT_BYTES:
            raise ImportValidationError('A fájl mérete legfeljebb 1,5 MB lehet.')
        return name

    def _read_rows(self, file_name, content):
        extension=PurePath(file_name).suffix.lower()
        if extension == '.csv':
            try:
                text=content.decode('utf-8-sig')
            except UnicodeDecodeError as exc:
                raise ImportValidationError('A CSV fájlnak UTF-8 kódolásúnak kell lennie.') from exc
            sample=text[:8192]
            try:
                dialect=csv.Sniffer().sniff(sample,delimiters=',;\t')
            except csv.Error:
                dialect=csv.excel
            reader=csv.DictReader(io.StringIO(text),dialect=dialect)
            header_map=self._map_headers(reader.fieldnames or [])
            output=[]
            for raw in reader:
                row={}
                for key,value in raw.items():
                    if key is not None:
                        row[header_map[self._header_key(key)]]=value
                if any(value and str(value).strip() for value in row.values()):
                    output.append(row)
            return output
        workbook=None
        try:
            workbook=load_workbook(io.BytesIO(content),read_only=True,data_only=True)
            sheet=workbook.active
            values=sheet.iter_rows(values_only=True)
            raw_headers=next(values,None)
            if not raw_headers:
                raise ImportValidationError('Az XLSX munkalap üres.')
            header_map=self._map_headers(raw_headers)
            keys=[header_map[self._header_key(value)] for value in raw_headers]
            output=[]
            for values_row in values:
                row=dict(zip(keys,values_row))
                if any(value is not None and str(value).strip() for value in row.values()):
                    output.append(row)
            return output
        except ImportValidationError:
            raise
        except Exception as exc:
            raise ImportValidationError(f'Az XLSX fájl nem olvasható: {exc}') from exc
        finally:
            if workbook is not None:
                workbook.close()

    def _map_headers(self, headers):
        mapped={}
        for header in headers:
            key=self._header_key(header)
            for canonical,aliases in self.HEADER_ALIASES.items():
                if key in aliases:
                    mapped[key]=canonical
                    break
            else:
                mapped[key]=key
        available=set(mapped.values())
        missing=self.REQUIRED_COLUMNS-available
        if missing:
            raise ImportValidationError('Hiányzó oszlop(ok): '+', '.join(sorted(missing)))
        return mapped

    @staticmethod
    def _header_key(value):
        decomposed=unicodedata.normalize('NFKD',str(value or '').strip().lower())
        plain=''.join(ch for ch in decomposed if not unicodedata.combining(ch))
        return ' '.join(re.sub(r'[^a-z0-9]+',' ',plain).split())

    def _normalize_row(self, row):
        normalized={self._header_key(key): value for key,value in row.items()}
        remapped={}
        for key,value in normalized.items():
            for canonical,aliases in self.HEADER_ALIASES.items():
                if key in aliases:
                    remapped[canonical]=value
                    break
            else:
                remapped[key]=value
        name=str(remapped.get('name') or '').strip()
        neptun=str(remapped.get('neptun') or '').strip().upper()
        email=str(remapped.get('email') or '').strip().lower() or None
        return {'name':name,'neptun':neptun,'email':email}

    @staticmethod
    def _validate_student(student):
        errors=[]
        if not student['name'] or len(student['name'])>160:
            errors.append(('name','A név kötelező, legfeljebb 160 karakter lehet.'))
        if not re.fullmatch(r'[A-Z0-9]{6}',student['neptun']):
            errors.append(('neptun','A Neptun-kód pontosan 6 betű vagy szám legyen.'))
        email=student.get('email')
        if email and (len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)):
            errors.append(('email','Érvénytelen e-mail-cím.'))
        return errors

    @staticmethod
    def _mark_repeated_values(rows, errors):
        seen_neptun={}; seen_email={}
        for item in rows:
            student=item['student']; number=item['row']
            for key,seen in [('neptun',seen_neptun),('email',seen_email)]:
                value=student.get(key)
                if not value:
                    continue
                if value in seen:
                    errors.append({'row':number,'field':key,'message':f'Duplikált {key} érték a fájlban (első sor: {seen[value]}).'})
                else:
                    seen[value]=number

    def _mark_existing_records(self, rows, errors):
        neptun=[item['student']['neptun'] for item in rows if item['student']['neptun']]
        emails=[item['student']['email'] for item in rows if item['student']['email']]
        existing_neptun=set(); existing_email=set()
        with self.db.cursor() as cursor:
            if neptun:
                marks=','.join(['%s']*len(neptun))
                cursor.execute(f'SELECT neptun FROM users WHERE neptun IN ({marks})',tuple(neptun))
                existing_neptun={row['neptun'] for row in cursor.fetchall()}
            if emails:
                marks=','.join(['%s']*len(emails))
                cursor.execute(f'SELECT email FROM users WHERE email IN ({marks})',tuple(emails))
                existing_email={row['email'].lower() for row in cursor.fetchall() if row['email']}
        for item in rows:
            student=item['student']; number=item['row']
            if student['neptun'] in existing_neptun:
                errors.append({'row':number,'field':'neptun','message':'Ez a Neptun-kód már szerepel az adatbázisban.'})
            if student['email'] and student['email'] in existing_email:
                errors.append({'row':number,'field':'email','message':'Ez az e-mail-cím már szerepel az adatbázisban.'})


