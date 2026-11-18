import argparse
import getpass
import json
import os
import sys
from utils.api_client import ApiClient,ApiError

def output(value):
    print(json.dumps(value,ensure_ascii=False,indent=2,default=str))

def parser():
    command=argparse.ArgumentParser(description='Egyetemi jelenlétkezelő API parancssori kliens')
    command.add_argument('--url',default=os.getenv('ATTENDANCE_API_URL','http://127.0.0.1:5000'))
    command.add_argument('--token',default=os.getenv('ATTENDANCE_API_TOKEN'))
    sub=command.add_subparsers(dest='command',required=True)
    sub.add_parser('login',help='Token kérése e-mail/jelszó alapján')
    sub.add_parser('me',help='Bejelentkezett fiók')
    sub.add_parser('users',help='Felhasználók keresése')
    users=sub.choices['users'];users.add_argument('--query');users.add_argument('--role');users.add_argument('--limit',type=int,default=100)
    sub.add_parser('courses',help='Kurzuslista')
    sessions=sub.add_parser('sessions',help='Kurzusalkalmak listája');sessions.add_argument('--course-id',type=int);sessions.add_argument('--state')
    sub.add_parser('inside',help='Jelenleg bent lévők')
    logs=sub.add_parser('logs',help='Legutóbbi ajtóesemények');logs.add_argument('--limit',type=int,default=50)
    scan=sub.add_parser('scan',help='Tesztkártya beolvasása API-n keresztül');scan.add_argument('card_uid')
    schedule=sub.add_parser('schedule',help='Heti alkalomsorozat ütemezése');schedule.add_argument('course_id',type=int);schedule.add_argument('first_start');schedule.add_argument('--weeks',type=int,default=12);schedule.add_argument('--duration',type=int,default=90);schedule.add_argument('--room')
    importer=sub.add_parser('import-students',help='Hallgatók előnézete és importálása');importer.add_argument('file')
    export=sub.add_parser('export-attendance',help='Alkalom jelenléti CSV exportja');export.add_argument('session_id',type=int);export.add_argument('--output',default='attendance.csv')
    return command

def main(argv=None):
    args=parser().parse_args(argv)
    client=ApiClient(args.url,args.token)
    try:
        if args.command=='login':
            email=input('E-mail: ');password=getpass.getpass('Jelszó: ')
            token=client.login(email,password);print(token);return 0
        if args.command=='import-students':
            preview=client.upload('/api/users/import/preview',args.file)
            output(preview)
            if not preview.get('can_import'):
                return 2
            if input('Importáljuk az előnézetben látható hallgatókat? [i/N] ').strip().lower()!='i':
                print('Import megszakítva.');return 0
            result=client.upload('/api/users/import/commit',args.file);output(result);return 0
        if args.command=='export-attendance':
            payload=client.request('GET',f'/api/export/sessions/{args.session_id}.csv')
            with open(args.output,'wb') as destination:destination.write(payload)
            print(f'Export elkészült: {args.output}');return 0
        routes={
            'me':('/api/auth/me',{}),
            'users':('/api/users/',{'q':args.query,'role':args.role,'limit':args.limit}),
            'courses':('/api/courses/',{}),
            'sessions':('/api/sessions/',{'course_id':args.course_id,'state':args.state}),
            'inside':('/api/access/inside',{}),
            'logs':('/api/access/logs',{'limit':args.limit}),
        }
        if args.command=='scan':
            result=client.request('POST','/api/access/scan',body={'card_id':args.card_uid})
        elif args.command=='schedule':
            result=client.request('POST',f'/api/sessions/courses/{args.course_id}/series',body={
                'first_start':args.first_start,'weeks':args.weeks,'duration_minutes':args.duration,'room':args.room})
        else:
            path,query=routes[args.command];result=client.request('GET',path,query=query)
        output(result);return 0
    except (ApiError,FileNotFoundError,ValueError) as exc:
        print(f'Hiba: {exc}',file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())

