import getpass
from services.auth_service import AuthService
from database.connection import Database

def main():
    email = input('Admin e-mail: ').strip().lower()
    name = input('Admin neve: ').strip()
    password = getpass.getpass('Új jelszó (legalább 8 karakter): ')
    encoded = AuthService().hash_password(password)
    with Database().cursor(commit=True) as cursor:
        cursor.execute('SELECT id FROM users WHERE email=%s', (email,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("UPDATE users SET name=%s,password_hash=%s,role='admin',active=1 WHERE id=%s", (name, encoded, existing['id']))
            print('A meglévő fiók adminisztrátorként frissült.')
        else:
            cursor.execute("INSERT INTO users(name,email,password_hash,role,active,is_inside) VALUES(%s,%s,%s,'admin',1,0)", (name, email, encoded))
            print('Adminisztrátori fiók létrehozva.')

if __name__ == '__main__':
    main()
