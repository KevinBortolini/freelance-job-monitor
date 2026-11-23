"""Optional Gmail adapter. All message/label operations are read-only."""
import base64
from dataclasses import dataclass
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
import tomllib
from types import SimpleNamespace
from .models import Alert, MonitorError
from .paths import project_path, private_path

SCOPES = ('https://www.googleapis.com/auth/gmail.readonly',)
TOKEN_URI = 'https://oauth2.googleapis.com/token'

@dataclass(frozen=True)
class LiveSettings:
    label: str
    query: str
    max_messages: int
    credentials_file: Path
    token_file: Path
    output_file: Path

def load_settings(path: Path) -> LiveSettings:
    try:
        raw = tomllib.loads(project_path(path).read_text(encoding='utf-8'))
        if set(raw) != {'label','query','max_messages','credentials_file','token_file','output_file'}:
            raise ValueError()
        if any(not isinstance(raw[k],str) for k in ['label','query','credentials_file','token_file','output_file']):
            raise ValueError()
        if not raw['label'].strip() or len(raw['label'])>200 or len(raw['query'])>1000 or any(ord(c)<32 for c in raw['label']+raw['query']):
            raise ValueError()
        if type(raw['max_messages']) is not int or not 1<=raw['max_messages']<=5000:raise ValueError()
        credentials,token,output=(private_path(raw[k]) for k in ['credentials_file','token_file','output_file'])
        if len({credentials,token,output})!=3 or credentials.suffix!='.json' or token.suffix!='.json' or output.suffix!='.xlsx':
            raise ValueError()
        return LiveSettings(raw['label'],raw['query'],raw['max_messages'],credentials,token,output)
    except MonitorError:raise
    except (OSError,ValueError,TypeError):
        raise MonitorError('Invalid live TOML configuration. Use the example schema, a nonempty label, and a message limit from 1 to 5000; private files must be distinct.') from None

def _read_json(path: Path):
    if path.stat().st_size>1000000:raise ValueError()
    result=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(result,dict):raise ValueError()
    return result

def _google_libraries():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        return SimpleNamespace(Request=Request,Credentials=Credentials,Flow=InstalledAppFlow,build=build)
    except ImportError:
        raise MonitorError('Live dependencies are missing. Install requirements-live.txt in the same environment.') from None

def _save_token(path: Path, text: str):
    temporary=None
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        with NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,prefix='.oauth-',suffix='.tmp',delete=False) as f:
            temporary=Path(f.name);os.chmod(temporary,0o600);f.write(text);f.flush();os.fsync(f.fileno())
        os.replace(temporary,path);temporary=None
    except OSError:
        raise MonitorError('Could not save local authorization securely. Existing token was not edited in place.') from None
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)

def create_service(settings: LiveSettings, *, authorize: bool = False):
    # Even programmatic callers cannot redirect OAuth storage into the original project.
    client_path,token_path=private_path(settings.credentials_file),private_path(settings.token_file)
    try:
        client=_read_json(client_path)['installed']
        if not isinstance(client,dict) or not client.get('client_id') or not client.get('client_secret'):
            raise ValueError()
        if client.get('token_uri')!=TOKEN_URI or client.get('auth_uri') not in {'https://accounts.google.com/o/oauth2/auth','https://accounts.google.com/o/oauth2/v2/auth'}:
            raise ValueError()
    except (OSError,ValueError,KeyError,TypeError):
        raise MonitorError('OAuth client configuration is missing or invalid. Use your own Google Desktop app JSON inside .local; contents are never printed.') from None
    sdk=_google_libraries();creds=None;changed=False
    if token_path.exists():
        try:
            token=_read_json(token_path)
            scopes=token.get('scopes',[])
            if isinstance(scopes,str):scopes=scopes.split()
            if set(scopes)!=set(SCOPES) or token.get('token_uri')!=TOKEN_URI or token.get('client_id')!=client['client_id']:
                raise ValueError()
            creds=sdk.Credentials.from_authorized_user_file(str(token_path),list(SCOPES))
        except Exception:
            raise MonitorError('Stored token is invalid, has different scopes, or belongs to another client. Preserve it privately, revoke the old grant if appropriate, and authorize again with a fresh token path.') from None
    if creds is not None and not creds.valid:
        if not (creds.expired and creds.refresh_token):
            raise MonitorError('Stored authorization cannot be refreshed. Revoke/remove your local token and run live --authorize again.')
        try:creds.refresh(sdk.Request());changed=True
        except Exception:
            raise MonitorError('Google authorization refresh failed or was revoked. No token was deleted. Check your account, revoke/remove your local token, then run live --authorize.') from None
    if creds is None:
        if not authorize:
            raise MonitorError('No local token exists. First authorization requires explicitly running live with --authorize.')
        try:
            flow=sdk.Flow.from_client_secrets_file(str(client_path),list(SCOPES))
            creds=flow.run_local_server(port=0,host='localhost',bind_addr='127.0.0.1',
                authorization_prompt_message='Authorize in the browser window for your own Google project.',
                success_message='Authorization received. You may close this window.',open_browser=True)
            changed=True
        except Exception:
            raise MonitorError('Interactive Google authorization failed. Check the Desktop client, test user, browser and local callback permissions. No email or credential details are printed.') from None
    if not creds.valid:
        raise MonitorError('Google did not return usable authorization. No mailbox request was made.')
    granted=getattr(creds,'granted_scopes',None)
    if granted and set(granted)!=set(SCOPES):
        raise MonitorError('Unexpected granted scopes. Review/revoke the grant before continuing.')
    if changed:_save_token(token_path,creds.to_json())
    try:return sdk.build('gmail','v1',credentials=creds,cache_discovery=False,static_discovery=True)
    except Exception:
        raise MonitorError('Could not initialize the Gmail client. Check live dependencies and your Google project.') from None

def _text_parts(payload):
    plain=[];html=[]
    def walk(part,depth=0):
        if depth>20:raise ValueError()
        if part.get('filename'):return
        mime=part.get('mimeType','')
        data=part.get('body',{}).get('data')
        if mime in {'text/plain','text/html'} and data:
            if not isinstance(data,str) or len(data)>1400000:raise ValueError()
            raw=base64.b64decode(data+'='*(-len(data)%4),altchars=b'-_',validate=True)
            charset='utf-8'
            for header in part.get('headers',[]):
                if header.get('name','').casefold()=='content-type':
                    from email.message import Message
                    message=Message();message['Content-Type']=header.get('value','');charset=message.get_content_charset() or charset
            text=raw.decode(charset,errors='replace')
            (html if mime=='text/html' else plain).append(text)
        for child in part.get('parts',[]):walk(child,depth+1)
    walk(payload)
    if sum(map(len,plain+html))>1000000:raise ValueError()
    return '\n'.join(plain),'\n'.join(html)

def iter_alerts(service, settings: LiveSettings):
    """Yield alert/diagnostic pairs; never modify labels, read state or messages."""
    try:
        users=service.users()
        labels=users.labels().list(userId='me').execute().get('labels',[])
        matches=[x['id'] for x in labels if x.get('name','').casefold()==settings.label.casefold()]
        if len(matches)!=1:
            raise MonitorError('Configured Gmail label is missing or ambiguous. Create/select it manually; the application does not create labels.')
        count=0;page=None;seen=set()
        while count<settings.max_messages:
            arguments={'userId':'me','labelIds':matches,'q':settings.query,'maxResults':min(500,settings.max_messages-count),'includeSpamTrash':False}
            if page:arguments['pageToken']=page
            response=users.messages().list(**arguments).execute()
            for item in response.get('messages',[]):
                if count>=settings.max_messages:break
                message=users.messages().get(userId='me',id=item['id'],format='full').execute();count+=1
                try:
                    payload=message['payload'];headers=payload.get('headers',[])
                    values={h['name'].casefold():h.get('value','') for h in headers}
                    plain,html=_text_parts(payload)
                    yield Alert(values.get('from',''),values.get('subject',''),plain,html),None
                except (ValueError,KeyError,TypeError,LookupError,UnicodeError):
                    yield None,'malformed_email'
            page=response.get('nextPageToken')
            if not page:break
            if page in seen:raise MonitorError('Gmail returned repeated pagination state; retry later. No workbook update was made.')
            seen.add(page)
        if count>=settings.max_messages:yield None,'message_limit_reached'
    except MonitorError:raise
    except Exception:
        raise MonitorError('Gmail read failed. Check authorization, API enablement, network and quotas. No mailbox changes were requested; retrying is safe for deduplication.') from None
