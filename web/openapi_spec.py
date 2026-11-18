
def build_openapi():
    bearer={'type':'http','scheme':'bearer','bearerFormat':'JWT'}
    secured=[{'BearerAuth':[]}]
    responses={
        '400':{'description':'Hibás vagy hiányos kérés.'},
        '401':{'description':'Hiányzó, lejárt vagy visszavont hitelesítési token.'},
        '403':{'description':'A szerepkör nem jogosult a műveletre.'},
        '500':{'description':'Váratlan szerverhiba.'},
    }
    def operation(summary,tag,*,security=True,body=None,parameters=None,success='200'):
        result={'summary':summary,'tags':[tag],'responses':{success:{'description':'Sikeres válasz'},**responses}}
        if security:
            result['security']=secured
        if body:
            result['requestBody']={'required':True,'content':{'application/json':{'schema':body}}}
        if parameters:
            result['parameters']=parameters
        return result
    id_parameter={'name':'id','in':'path','required':True,'schema':{'type':'integer','minimum':1}}
    paths={
        '/api/health':{'get':operation('Liveness ellenőrzés','Rendszer',security=False)},
        '/api/health/details':{'get':operation('Részletes rendszerállapot','Rendszer')},
        '/api/auth/login':{'post':operation('Bejelentkezés és token létrehozása','Hitelesítés',security=False,success='200',body={'type':'object','required':['email','password'],'properties':{'email':{'type':'string','format':'email'},'password':{'type':'string','format':'password'}}})},
        '/api/auth/me':{'get':operation('Saját fiók lekérdezése','Hitelesítés')},
        '/api/auth/logout':{'post':operation('Token visszavonása','Hitelesítés')},
        '/api/auth/change-password':{'post':operation('Jelszó módosítása','Hitelesítés',body={'type':'object','required':['current_password','new_password'],'properties':{'current_password':{'type':'string'},'new_password':{'type':'string','minLength':8,'maxLength':72}}})},
        '/api/users/':{'get':operation('Hallgatók és oktatók listázása','Felhasználók',parameters=[{'name':'q','in':'query','schema':{'type':'string'}},{'name':'role','in':'query','schema':{'type':'string','enum':['student','teacher','all']}},{'name':'limit','in':'query','schema':{'type':'integer','default':100}},{'name':'offset','in':'query','schema':{'type':'integer','default':0}}]),'post':operation('Hallgató vagy oktató létrehozása admin jogosultsággal','Felhasználók',body={'$ref':'#/components/schemas/UserInput'},success='201')},
        '/api/users/{id}':{'get':operation('Felhasználó lekérése','Felhasználók',parameters=[id_parameter]),'patch':operation('Felhasználó frissítése','Felhasználók',parameters=[id_parameter],body={'$ref':'#/components/schemas/UserInput'})},
        '/api/users/{id}/assign_card':{'post':operation('Kártya hozzárendelése','Felhasználók',parameters=[id_parameter],body={'type':'object','required':['card_id'],'properties':{'card_id':{'type':'string','maxLength':64}}})},
        '/api/courses/':{'get':operation('Kurzuslista','Kurzusok'),'post':operation('Kurzus létrehozása','Kurzusok',body={'$ref':'#/components/schemas/CourseInput'},success='201')},
        '/api/courses/{id}/students':{'get':operation('Kurzusnévsor','Kurzusok',parameters=[id_parameter])},
        '/api/courses/{id}/students/bulk':{'post':operation('Csoportos kurzusfelvétel','Kurzusok',parameters=[id_parameter],body={'type':'object','required':['user_ids'],'properties':{'user_ids':{'type':'array','maxItems':500,'items':{'type':'integer'}}}},success='201')},
        '/api/sessions/':{'get':operation('Kurzusalkalmak keresése','Alkalmak')},
        '/api/sessions/courses/{id}':{'post':operation('Kurzusalkalom ütemezése','Alkalmak',parameters=[id_parameter],body={'$ref':'#/components/schemas/SessionInput'},success='201')},
        '/api/sessions/courses/{id}/series':{'post':operation('Heti alkalomsorozat ütemezése','Alkalmak',parameters=[id_parameter],body={'type':'object','required':['first_start','weeks','duration_minutes'],'properties':{'first_start':{'type':'string','format':'date-time'},'weeks':{'type':'integer','minimum':1,'maximum':20},'duration_minutes':{'type':'integer','minimum':15,'maximum':360},'room':{'type':'string'}}},success='201')},
        '/api/sessions/{id}':{'get':operation('Jelenléti ív lekérése','Jelenlét',parameters=[id_parameter])},
        '/api/sessions/{id}/scan':{'post':operation('Órai NFC-kártya beolvasása','Jelenlét',parameters=[id_parameter],body={'type':'object','required':['card_id'],'properties':{'card_id':{'type':'string'}}})},
        '/api/sessions/{id}/attendance/{user_id}':{'put':operation('Jelenléti állapot javítása','Jelenlét',parameters=[id_parameter,{'name':'user_id','in':'path','required':True,'schema':{'type':'integer'}}],body={'type':'object','required':['status'],'properties':{'status':{'type':'string','enum':['absent','present','late','excused']},'note':{'type':'string','maxLength':500}}})},
        '/api/users/import/preview':{'post':operation('Hallgatói fájl előnézete','Import',success='200')},
        '/api/users/import/commit':{'post':operation('Hallgatói import mentése','Import',success='201')},
        '/api/export/calendar.ics':{'get':operation('Kurzusnaptár exportja','Export')},
    }
    schemas={
        'UserInput':{'type':'object','required':['name'],'properties':{'name':{'type':'string','maxLength':160},'email':{'type':'string','format':'email'},'password':{'type':'string','format':'password','minLength':8,'maxLength':72},'neptun':{'type':'string','pattern':'^[A-Z0-9]{6}$'},'role':{'type':'string','enum':['student','teacher']}}},
        'CourseInput':{'type':'object','required':['code','name'],'properties':{'code':{'type':'string','maxLength':32},'name':{'type':'string','maxLength':160},'description':{'type':'string','maxLength':4000},'teacher_id':{'type':'integer'}}},
        'SessionInput':{'type':'object','required':['starts_at','ends_at'],'properties':{'starts_at':{'type':'string','format':'date-time'},'ends_at':{'type':'string','format':'date-time'},'title':{'type':'string','maxLength':160},'room':{'type':'string','maxLength':80},'late_after_minutes':{'type':'integer','minimum':0,'maximum':180}}},
        'AttendanceState':{'type':'string','enum':['absent','present','late','excused']},
        'ApiError':{'type':'object','properties':{'error':{'type':'string'},'message':{'type':'string'}}},
    }
    return {'openapi':'3.0.3','info':{'title':'Egyetemi jelenlétkezelő API','version':'1.0.0','description':'NFC-alapú jelenléti, kurzus- és adminisztrációs végpontok.'},'servers':[{'url':'/'}],'paths':paths,'components':{'securitySchemes':{'BearerAuth':bearer},'schemas':schemas}}
