import argparse
import secrets
from datetime import datetime,timedelta
from database.connection import Database

DEMO_TEACHER_EMAIL='oktato.demo@uni.invalid'
DEMO_COURSES=[('DEMO01','NFC jelenléti rendszer bemutató'),
              ('DEMO02','Adatbázis és webprogramozás bemutató')]

def seed_demo(student_count=24,*,confirm=False,db=None):
    if not confirm:
        raise ValueError('Az adatbázis írásához add meg a --confirm kapcsolót.')
    student_count=max(1,min(int(student_count),200))
    database=db or Database()
    with database.cursor(commit=True) as cursor:
        cursor.execute('SELECT id FROM users WHERE email=%s',(DEMO_TEACHER_EMAIL,))
        teacher=cursor.fetchone()
        if teacher:
            teacher_id=teacher['id']
        else:
            cursor.execute("INSERT INTO users(name,email,role,active,is_inside) VALUES('Demó Oktató',%s,'teacher',1,0)",(DEMO_TEACHER_EMAIL,))
            teacher_id=cursor.lastrowid
        course_ids=[]
        for code,name in DEMO_COURSES:
            cursor.execute('SELECT id FROM courses WHERE code=%s',(code,))
            course=cursor.fetchone()
            if course:
                course_id=course['id']
            else:
                cursor.execute('INSERT INTO courses(code,name,teacher_id,active,description) VALUES(%s,%s,%s,1,%s)',(code,name,teacher_id,'Automatikusan generált, fiktív demonstrációs kurzus.'))
                course_id=cursor.lastrowid
            course_ids.append(course_id)
        students=[]
        for number in range(1,student_count+1):
            email=f'demo.student.{number:03d}@uni.invalid'
            neptun='D'+''.join(secrets.choice('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ') for _ in range(5))
            cursor.execute('SELECT id FROM users WHERE email=%s',(email,))
            existing=cursor.fetchone()
            if existing:
                user_id=existing['id']
            else:
                cursor.execute('INSERT INTO users(name,email,neptun,role,active,is_inside) VALUES(%s,%s,%s,\'student\',1,0)',
                               (f'Demó Hallgató {number:03d}',email,neptun))
                user_id=cursor.lastrowid
            students.append(user_id)
        for course_id in course_ids:
            for user_id in students:
                cursor.execute("INSERT IGNORE INTO enrollments(user_id,course_id,enrollment_status) VALUES(%s,%s,'active')",(user_id,course_id))
            cursor.execute('SELECT id FROM course_sessions WHERE course_id=%s AND title=%s LIMIT 1',(course_id,'Demonstrációs múltbeli alkalom'))
            if cursor.fetchone():
                continue
            for week in range(4,0,-1):
                starts=(datetime.now()-timedelta(days=7*week)).replace(hour=9,minute=0,second=0,microsecond=0)
                ends=starts+timedelta(minutes=90)
                cursor.execute("INSERT INTO course_sessions(course_id,title,starts_at,ends_at,room,status,late_after_minutes,created_by) VALUES(%s,'Demonstrációs múltbeli alkalom',%s,%s,'DEMO-01','closed',10,%s)",
                               (course_id,starts,ends,teacher_id))
                session_id=cursor.lastrowid
                for index,user_id in enumerate(students):
                    status='absent' if index%7==0 else ('late' if index%5==0 else 'present')
                    marked_at=starts+timedelta(minutes=18) if status=='late' else (starts+timedelta(minutes=3) if status=='present' else None)
                    cursor.execute('INSERT INTO attendance_records(session_id,user_id,status,marked_at,marked_by,method,note) VALUES(%s,%s,%s,%s,%s,\'manual\',%s)',
                                   (session_id,user_id,status,marked_at,teacher_id,'Szintetikus demóadat' if status=='absent' else None))
                    cursor.execute('INSERT INTO attendance_history(session_id,user_id,actor_id,previous_status,new_status,source,reason) VALUES(%s,%s,%s,NULL,%s,\'system\',\'Demóadat-generálás\')',
                                   (session_id,user_id,teacher_id,status))
    return {'students':student_count,'courses':len(course_ids),'sessions':len(course_ids)*4,
            'note':'Minden létrehozott hallgatói fiók és jelenléti esemény fiktív.'}

def main():
    parser=argparse.ArgumentParser(description='Fiktív kurzus- és jelenléti adatok létrehozása')
    parser.add_argument('--students',type=int,default=24)
    parser.add_argument('--confirm',action='store_true',help='Engedélyezi a szintetikus sorok adatbázisba írását')
    args=parser.parse_args()
    try:
        print(seed_demo(args.students,confirm=args.confirm))
        return 0
    except ValueError as exc:
        parser.error(str(exc))

if __name__=='__main__':
    raise SystemExit(main())
