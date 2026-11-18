import argparse
from pathlib import Path
import mysql.connector
from mysql.connector import Error
from config.config import Config

class SchemaInitializationError(RuntimeError):
    pass

def split_statements(sql_text):
    statements=[]
    buffer=[]
    for line in sql_text.splitlines():
        trimmed=line.strip()
        if not trimmed or trimmed.startswith('--') or trimmed.startswith('/*') or trimmed.startswith('*/'):
            continue
        buffer.append(line)
        if trimmed.endswith(';'):
            statement='\n'.join(buffer).strip()
            if statement:
                statements.append(statement[:-1].strip())
            buffer=[]
    trailing='\n'.join(buffer).strip()
    if trailing:
        statements.append(trailing)
    return statements

def initialize_schema(schema_path=None,dry_run=False):
    path=Path(schema_path) if schema_path else Config.BASE_DIR/'database'/'database.sql'
    if not path.is_file():
        raise SchemaInitializationError(f'Sémafájl nem található: {path}')
    statements=split_statements(path.read_text(encoding='utf-8-sig'))
    if dry_run:
        return {'path':str(path),'statements':len(statements),'executed':False}
    options=Config.database_options().copy()
    options.pop('database',None)
    connection=None
    try:
        connection=mysql.connector.connect(**options)
        cursor=connection.cursor()
        for index,statement in enumerate(statements,start=1):
            try:
                cursor.execute(statement)
                if statement.lstrip().upper().startswith(('CREATE DATABASE','USE ')):
                    connection.commit()
            except Error as exc:
                connection.rollback()
                raise SchemaInitializationError(f'{index}. SQL utasítás sikertelen: {exc}') from exc
        connection.commit()
        cursor.close()
        return {'path':str(path),'statements':len(statements),'executed':True,
                'database':Config.DB_NAME}
    except Error as exc:
        raise SchemaInitializationError(f'MySQL kapcsolódási hiba: {exc}') from exc
    finally:
        if connection is not None:
            connection.close()

def main():
    parser=argparse.ArgumentParser(description='Üres egyetemi jelenléti adatbázis létrehozása')
    parser.add_argument('--schema',help='Alternatív SQL fájl')
    parser.add_argument('--dry-run',action='store_true',help='Csak az utasítások számát mutatja')
    args=parser.parse_args()
    try:
        print(initialize_schema(args.schema,args.dry_run))
        return 0
    except SchemaInitializationError as exc:
        parser.exit(1,f'Hiba: {exc}\n')

if __name__=='__main__':
    raise SystemExit(main())
