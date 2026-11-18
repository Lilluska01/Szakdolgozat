import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

class ApiError(RuntimeError):
    def __init__(self,status,message,payload=None):
        super().__init__(message)
        self.status=status
        self.payload=payload or {}

class ApiClient:
    def __init__(self,base_url='http://127.0.0.1:5000',token=None,timeout=20):
        self.base_url=base_url.rstrip('/')
        self.token=token
        self.timeout=timeout

    def login(self,email,password):
        result=self.request('POST','/api/auth/login',body={'email':email,'password':password},authenticated=False)
        self.token=result['token']
        return self.token

    def current_user(self):
        return self.request('GET','/api/auth/me')

    def request(self,method,path,*,body=None,query=None,authenticated=True,headers=None):
        url=self.base_url+path
        if query:
            encoded=urllib.parse.urlencode({key:value for key,value in query.items() if value is not None})
            if encoded:
                url+='?'+encoded
        request_headers={'Accept':'application/json'}
        if authenticated and self.token:
            request_headers['Authorization']='Bearer '+self.token
        if headers:
            request_headers.update(headers)
        data=None
        if body is not None:
            data=json.dumps(body,ensure_ascii=False).encode('utf-8')
            request_headers['Content-Type']='application/json; charset=utf-8'
        request=urllib.request.Request(url,data=data,headers=request_headers,method=method.upper())
        try:
            with urllib.request.urlopen(request,timeout=self.timeout) as response:
                payload=response.read()
                if not payload:
                    return {'status':'ok'}
                content_type=response.headers.get('Content-Type','')
                if 'json' in content_type:
                    return json.loads(payload.decode('utf-8'))
                return payload
        except urllib.error.HTTPError as exc:
            raw=exc.read()
            try:
                payload=json.loads(raw.decode('utf-8'))
            except (UnicodeDecodeError,json.JSONDecodeError):
                payload={'message':raw.decode('utf-8',errors='replace')}
            raise ApiError(exc.code,payload.get('message') or payload.get('error') or exc.reason,payload) from exc
        except urllib.error.URLError as exc:
            raise ApiError(0,f'Nem érhető el az API: {exc.reason}') from exc

    def upload(self,path,file_path,field='file'):
        file_path=Path(file_path)
        if not file_path.is_file():
            raise FileNotFoundError(file_path)
        boundary='----AttendanceClientBoundary7MA4YWxkTrZu0gW'
        content=file_path.read_bytes()
        mime=mimetypes.guess_type(file_path.name)[0] or 'application/octet-stream'
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
              f'filename="{file_path.name}"\r\nContent-Type: {mime}\r\n\r\n').encode('utf-8')
        body+=content+f'\r\n--{boundary}--\r\n'.encode('ascii')
        request_headers={'Content-Type':f'multipart/form-data; boundary={boundary}',
                         'Accept':'application/json'}
        if self.token:
            request_headers['Authorization']='Bearer '+self.token
        request=urllib.request.Request(self.base_url+path,data=body,headers=request_headers,method='POST')
        try:
            with urllib.request.urlopen(request,timeout=self.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            payload=json.loads(exc.read().decode('utf-8',errors='replace'))
            raise ApiError(exc.code,payload.get('message') or payload.get('error','Hiba'),payload) from exc

    def logout(self):
        result=self.request('POST','/api/auth/logout',body={})
        self.token=None
        return result
