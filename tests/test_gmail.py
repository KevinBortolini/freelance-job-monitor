import base64
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import shutil
import pytest
from job_monitor.models import MonitorError
from job_monitor.paths import ROOT
from job_monitor.gmail import LiveSettings,SCOPES,TOKEN_URI,load_settings,create_service,iter_alerts

@pytest.fixture
def settings():
    directory=ROOT/'.local'/('mock-test-'+uuid4().hex);directory.mkdir(parents=True)
    client={'installed':{'client_id':'fictional-client','client_secret':'fictional-test-only','auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':TOKEN_URI}}
    (directory/'client.json').write_text(json.dumps(client))
    yield LiveSettings('JobAlerts','newer_than:30d',10,directory/'client.json',directory/'token.json',directory/'output.xlsx')
    shutil.rmtree(directory)

def token_data():
    return {'token':'fictional-access','refresh_token':'fictional-refresh','client_id':'fictional-client','client_secret':'fictional-test-only','token_uri':TOKEN_URI,'scopes':list(SCOPES)}

def sdk_for(monkeypatch,*,valid=True,expired=False,refresh_error=False):
    import job_monitor.gmail as module
    creds=SimpleNamespace(valid=valid,expired=expired,refresh_token='fictional-refresh',granted_scopes=list(SCOPES),to_json=lambda:json.dumps(token_data()))
    def refresh(request):
        if refresh_error:raise Exception('SECRET_BODY_AND_TOKEN_MUST_NOT_APPEAR')
        creds.valid=True
    creds.refresh=Mock(side_effect=refresh)
    flow=Mock();flow.run_local_server.return_value=creds
    sdk=SimpleNamespace(Credentials=Mock(),Flow=Mock(),Request=Mock(),build=Mock(return_value='mock-service'))
    sdk.Credentials.from_authorized_user_file.return_value=creds;sdk.Flow.from_client_secrets_file.return_value=flow
    monkeypatch.setattr(module,'_google_libraries',lambda:sdk)
    return sdk,creds,flow

def test_first_authorization_requires_explicit_flag(settings,monkeypatch):
    sdk,creds,flow=sdk_for(monkeypatch)
    with pytest.raises(MonitorError,match='--authorize'):create_service(settings)
    flow.run_local_server.assert_not_called();sdk.build.assert_not_called()
    assert not settings.token_file.exists()

def test_explicit_authorization_scopes_callback_and_private_token(settings,monkeypatch):
    import job_monitor.gmail as module
    permissions=[];real_chmod=module.os.chmod
    def chmod(path,mode):
        permissions.append(mode);return real_chmod(path,mode)
    monkeypatch.setattr(module.os,'chmod',chmod)
    sdk,creds,flow=sdk_for(monkeypatch)
    assert create_service(settings,authorize=True)=='mock-service'
    sdk.Flow.from_client_secrets_file.assert_called_once_with(str(settings.credentials_file),list(SCOPES))
    args=flow.run_local_server.call_args.kwargs
    assert args['port']==0 and args['bind_addr']=='127.0.0.1' and args['open_browser']
    assert '{url}' not in args['authorization_prompt_message']
    assert json.loads(settings.token_file.read_text())['scopes']==list(SCOPES)
    # NTFS/Windows mounts can ignore POSIX mode bits; enforce the requested call,
    # without claiming that an OS ACL was verified by this mocked flow.
    assert 0o600 in permissions
    assert sdk.build.call_args.kwargs['static_discovery'] is True

def test_valid_token_reuses_authorization_without_prompt(settings,monkeypatch):
    settings.token_file.write_text(json.dumps(token_data()));sdk,creds,flow=sdk_for(monkeypatch)
    assert create_service(settings)=='mock-service'
    flow.run_local_server.assert_not_called();creds.refresh.assert_not_called()

def test_expired_token_refresh_and_revocation_failure(settings,monkeypatch):
    settings.token_file.write_text(json.dumps(token_data()));sdk,creds,flow=sdk_for(monkeypatch,valid=False,expired=True)
    create_service(settings);creds.refresh.assert_called_once();flow.run_local_server.assert_not_called()
    before=settings.token_file.read_bytes()
    sdk_for(monkeypatch,valid=False,expired=True,refresh_error=True)
    with pytest.raises(MonitorError) as error:create_service(settings,authorize=True)
    assert 'SECRET' not in str(error.value) and 'refresh failed' in str(error.value)
    assert settings.token_file.read_bytes()==before

@pytest.mark.parametrize('patch',[{'scopes':['https://mail.google.com/']},{'client_id':'another-fictional-client'},{'token_uri':'https://invalid.example/token'}])
def test_foreign_or_overprivileged_tokens_rejected(settings,monkeypatch,patch):
    value=token_data();value.update(patch);settings.token_file.write_text(json.dumps(value));sdk,creds,flow=sdk_for(monkeypatch)
    with pytest.raises(MonitorError,match='Stored token'):create_service(settings)
    sdk.Credentials.from_authorized_user_file.assert_not_called()

def test_oauth_and_api_errors_never_echo_payload(settings,monkeypatch):
    sdk,creds,flow=sdk_for(monkeypatch);flow.run_local_server.side_effect=Exception('PRIVATE_OAUTH_VALUE')
    with pytest.raises(MonitorError) as error:create_service(settings,authorize=True)
    assert 'PRIVATE' not in str(error.value)
    settings.credentials_file.write_text('{invalid PRIVATE_CONFIGURATION')
    with pytest.raises(MonitorError) as error:create_service(settings,authorize=True)
    assert 'PRIVATE_CONFIGURATION' not in str(error.value)

def test_settings_required_fields_boundaries_and_no_overwrite(settings):
    path=settings.credentials_file.parent/'live.toml'
    text=f'label="JobAlerts"\nquery="newer_than:30d"\nmax_messages=10\ncredentials_file="{settings.credentials_file.as_posix()}"\ntoken_file="{settings.token_file.as_posix()}"\noutput_file="{settings.output_file.as_posix()}"\n'
    path.write_text(text);before=path.read_bytes();assert load_settings(path)==settings;assert path.read_bytes()==before
    for invalid in [text+'unknown=true\n',text.replace('max_messages=10','max_messages=0'),text.replace(settings.token_file.as_posix(),settings.credentials_file.as_posix()),text.replace('label="JobAlerts"','label=""'),text.replace(settings.output_file.as_posix(),(ROOT.parent/'private.xlsx').as_posix())]:
        path.write_text(invalid)
        with pytest.raises(MonitorError):load_settings(path)

class Request:
    def __init__(self,value):self.value=value
    def execute(self):
        if isinstance(self.value,Exception):raise self.value
        return self.value

class ReadOnlyAPI:
    def __init__(self,pages,bodies,labels=None):
        self.pages=iter(pages);self.bodies=bodies;self.calls=[]
        self.label_values=labels if labels is not None else [{'name':'JobAlerts','id':'fictional-label'}]
    def users(self):return self
    def labels(self):return SimpleNamespace(list=lambda **kwargs:Request({'labels':self.label_values}))
    def messages(self):return self
    def list(self,**kwargs):self.calls.append(('list',kwargs));return Request(next(self.pages))
    def get(self,**kwargs):self.calls.append(('get',kwargs));return Request(self.bodies[kwargs['id']])
    # No mutation methods are defined: any unexpected operation fails the test.

def payload(text='Invented digest'):
    encoded=base64.urlsafe_b64encode(text.encode()).decode().rstrip('=')
    return {'payload':{'mimeType':'multipart/alternative','headers':[{'name':'From','value':'alerts@freelancer.com'},{'name':'Subject','value':'Invented'}],
        'parts':[{'mimeType':'text/plain','body':{'data':encoded}},{'mimeType':'text/html','body':{'data':encoded}}]}}

def test_paginated_read_query_label_and_nested_mime(settings):
    api=ReadOnlyAPI([{'messages':[{'id':'a'}],'nextPageToken':'p2'},{'messages':[{'id':'b'}]}],{'a':payload(),'b':payload()})
    rows=list(iter_alerts(api,settings));assert len(rows)==2 and all(x[0].plain=='Invented digest' and x[0].html=='Invented digest' for x in rows)
    lists=[args for name,args in api.calls if name=='list'];assert lists[0]['labelIds']==['fictional-label']
    assert lists[0]['q']=='newer_than:30d' and lists[0]['includeSpamTrash'] is False
    assert lists[1]['pageToken']=='p2' and lists[1]['maxResults']==9
    assert all(args['format']=='full' and args['userId']=='me' for name,args in api.calls if name=='get')

@pytest.mark.parametrize('labels',[[],[{'name':'JobAlerts','id':'a'},{'name':'jobalerts','id':'b'}]])
def test_missing_ambiguous_label_never_created(settings,labels):
    api=ReadOnlyAPI([],{},labels)
    with pytest.raises(MonitorError,match='label'):list(iter_alerts(api,settings))
    assert not api.calls

def test_limit_bad_mime_attachment_and_safe_api_failure(settings):
    bad=payload();bad['payload']['parts'][0]['body']['data']='%%INVALID%%'
    api=ReadOnlyAPI([{'messages':[{'id':'bad'},{'id':'good'}]}],{'bad':bad,'good':payload()})
    rows=list(iter_alerts(api,replace(settings,max_messages=1)))
    assert rows==[(None,'malformed_email'),(None,'message_limit_reached')]
    attachment=payload();attachment['payload']['parts'].append({'mimeType':'text/plain','filename':'invented.txt','body':{'data':'INVALID'}})
    assert list(iter_alerts(ReadOnlyAPI([{'messages':[{'id':'a'}]}],{'a':attachment}),settings))[0][0].plain=='Invented digest'
    failure=ReadOnlyAPI([Exception('SECRET_MAIL_SUBJECT_TOKEN')],{})
    with pytest.raises(MonitorError) as error:list(iter_alerts(failure,settings))
    assert 'SECRET' not in str(error.value)

def test_repeated_page_token_fails_safely(settings):
    api=ReadOnlyAPI([{'nextPageToken':'same'},{'nextPageToken':'same'}],{})
    with pytest.raises(MonitorError,match='repeated pagination'):list(iter_alerts(api,settings))
