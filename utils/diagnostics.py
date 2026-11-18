import argparse
import importlib.util
import os
import sys
from config.config import Config

REQUIRED_MODULES=('flask','mysql.connector','jwt','bcrypt','openpyxl')

def module_available(name):
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError,ModuleNotFoundError,ValueError):
        return False

def inspect_environment():
    checks=[]
    checks.append(('Python',sys.version_info >= (3,11),sys.version.split()[0]))
    for module in REQUIRED_MODULES:
        checks.append((f'Python csomag: {module}',module_available(module),'telepítve' if module_available(module) else 'hiányzik'))
    secret_ok=Config.SECRET_KEY!='change-this-development-secret'
    checks.append(('Saját SECRET_KEY',secret_ok,'beállítva' if secret_ok else 'fejlesztői alapérték'))
    db_configured=bool(Config.DB_HOST and Config.DB_NAME and Config.DB_USER)
    checks.append(('MySQL beállítások',db_configured,Config.DB_HOST+'/'+Config.DB_NAME))
    checks.append(('SQL-séma fájl', (Config.BASE_DIR/'database'/'database.sql').is_file(),'database/database.sql'))
    return checks

def main():
    parser=argparse.ArgumentParser(description='Helyi projektkonfiguráció ellenőrzése')
    parser.add_argument('--strict',action='store_true',help='Hibakód visszaadása figyelmeztetés esetén is')
    args=parser.parse_args()
    checks=inspect_environment()
    for name,ok,detail in checks:
        print(f"{'OK' if ok else 'FIGYELEM':10} {name:30} {detail}")
    failures=sum(not ok for _,ok,_ in checks)
    return 1 if args.strict and failures else 0

if __name__=='__main__':
    raise SystemExit(main())
