#!/usr/bin/env python3
"""Official OAuth desktop flow / resumable HTTPS transport. Never auto-enabled.

Optional Google-maintained OAuth/auth libraries; dry-run factory needs neither.
Credentials and resumable URLs use Windows DPAPI (current user). No plaintext
fallback. No OAuth tokens, client secrets or upload URLs are printed or audited.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
import factory_orchestrator as f
import youtube_factory as yt

READ_SCOPE='https://www.googleapis.com/auth/youtube.readonly'
# videos.update requires force-ssl (upload-only scope cannot schedule).
WRITE_SCOPE='https://www.googleapis.com/auth/youtube.force-ssl'


def dpapi(data, decrypt=False):
    if os.name!='nt': raise ValueError('Secure Windows DPAPI storage required; no plaintext fallback')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(data); source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte))); target=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True); kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p]; kernel.LocalFree.restype=ctypes.c_void_p
    fn=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    fn.restype=wintypes.BOOL
    # CRYPTPROTECT_UI_FORBIDDEN; current-user scope, never LOCAL_MACHINE.
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):
        raise ValueError('Windows credential protection failed')
    try: return ctypes.string_at(target.data,target.size)
    finally: kernel.LocalFree(target.data)


class Vault:
    def __init__(self,root):
        self.root=Path(root).resolve(); f.init(self.root)
        self.path=f.owned(root,'youtube-secrets'); self.path.mkdir(exist_ok=True)

    def save(self,name,value):
        f.identifier(name); target=f.owned(self.path,name+'.bin'); raw=dpapi(json.dumps(value).encode())
        temp=target.with_suffix('.partial');
        with temp.open('wb') as out: out.write(raw);out.flush();os.fsync(out.fileno())
        os.replace(temp,target)
        return name

    def load(self,name):
        f.identifier(name); return json.loads(dpapi(f.owned(self.path,name+'.bin').read_bytes(),decrypt=True))


def authenticated(root,alias):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import AuthorizedSession,Request
    vault=Vault(root); data=vault.load(alias); creds=Credentials.from_authorized_user_info(data)
    if not creds.valid:
        if not creds.refresh_token: raise ValueError('Reconnect this channel personally through OAuth')
        try: creds.refresh(Request())
        except Exception: raise ValueError('OAuth refresh failed; reconnect personally, no automated consent') from None
        vault.save(alias,json.loads(creds.to_json()))
    return AuthorizedSession(creds),vault,creds


def checked_response(response,allowed=(200,201,204,308)):
    if response.status_code in (429,500,502,503,504):
        delay=response.headers.get('Retry-After','60')
        if not str(delay).isdigit(): delay=60
        raise yt.RetryLater(delay)
    if response.status_code not in allowed:
        raise ValueError('YouTube HTTP '+str(response.status_code)+'; credentials and response body omitted')
    return response


def channel_identity(session):
    response=checked_response(session.get('https://www.googleapis.com/youtube/v3/channels',params={'part':'id,snippet','mine':'true'},timeout=45,allow_redirects=False))
    items=response.json().get('items',[])
    if len(items)!=1 or not yt.CHANNEL_ID.fullmatch(items[0].get('id','')):
        raise ValueError('Choose one exact YouTube/Brand channel and authorize it separately')
    return items


def oauth_connect(root,client_json,role,confirmed_channel,write=False):
    """User invokes locally. Browser handles account/Brand selection and consent."""
    if os.name!='nt': raise ValueError('This installer targets Windows; no insecure credential fallback')
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import AuthorizedSession
    data=f.read(client_json)
    config=data.get('installed',{})
    if (not str(config.get('client_id','')).endswith('.apps.googleusercontent.com') or
        config.get('auth_uri')!='https://accounts.google.com/o/oauth2/auth' or
        config.get('token_uri')!='https://oauth2.googleapis.com/token'):
        raise ValueError('Use an official Google Desktop OAuth client configuration')
    if role not in f.CHANNELS or not yt.CHANNEL_ID.fullmatch(confirmed_channel):
        raise ValueError('Supply the intended factory role and exact channel ID before consent')
    scope=WRITE_SCOPE if write else READ_SCOPE
    flow=InstalledAppFlow.from_client_config(data,[scope],autogenerate_code_verifier=True)
    creds=flow.run_local_server(host='127.0.0.1',port=0,open_browser=True,timeout_seconds=180,
        authorization_prompt_message='Completa personalmente la selección de cuenta/canal y el consentimiento en Google.',
        success_message='Consentimiento recibido. Puedes cerrar esta pestaña.',access_type='offline',prompt='consent')
    observed=channel_identity(AuthorizedSession(creds))
    if observed[0]['id']!=confirmed_channel:
        raise ValueError('Authorized channel differs from the ID you chose; nothing was mapped or stored')
    alias='oauth_'+role+('_write' if write else '_read'); Vault(root).save(alias,json.loads(creds.to_json()))
    # Read-only mapping is kept separate until the user explicitly adds write scope.
    # A ready live plan pins the write credential alias; no upload happens here.
    if write:
        result=yt.bind_channel(root,role,observed,confirmed_channel,alias,'oauth')
    else:
        result={'role':role,'channelId':confirmed_channel,'title':observed[0]['snippet']['title'],'credentialRef':alias,'writeAuthorized':False}
        observed_path=f.owned(root,'youtube-channel-observations',role+'.json');observed_path.parent.mkdir(exist_ok=True)
        f.render.atomic_json(observed_path,result)
    return result


class OfficialTransport:
    origin='live'
    chunk_size=8*1024*1024  # fixed multiple of 256KiB

    def __init__(self,root,batch):
        info=yt.batch_info(root,batch)
        if info['origin']!='live': raise ValueError('Cannot send a simulated plan to YouTube')
        yt.live_approval(root,info)
        if info['approval']!=info['sha']: raise ValueError('Exact plan approval is missing')
        self.session,self.vault,self.creds=authenticated(root,info['plan']['credentialRef'])
        if not self.creds.has_scopes([WRITE_SCOPE]): raise ValueError('Explicit scheduling permission not granted')

    def channel_id(self): return channel_identity(self.session)[0]['id']

    def send(self,method,url,**kwargs):
        try: return getattr(self.session,method)(url,**kwargs)
        except Exception as error:
            # A lost final response must resume the saved URI, never insert again.
            from requests.exceptions import RequestException
            if isinstance(error,RequestException): raise yt.RetryLater(60) from None
            raise ValueError('Authorized transport failed; reconnect/review locally') from None

    def start(self,spec,item_id):
        if spec['body']['status'].get('privacyStatus')!='private' or 'publishAt' in spec['body']['status']:
            raise ValueError('Every initial upload must be private and unscheduled')
        r=checked_response(self.send('post','https://www.googleapis.com/upload/youtube/v3/videos',
          params={'uploadType':'resumable','part':'snippet,status','notifySubscribers':'false'},json=spec['body'],
          headers={'X-Upload-Content-Length':str(spec['bytes']),'X-Upload-Content-Type':'video/mp4'},timeout=60,allow_redirects=False))
        location=r.headers.get('Location',''); self.validate_uri(location)
        # Only the local opaque reference enters SQLite. The URI is a credential.
        ref='session_'+f.fingerprint(item_id)[:24];self.vault.save(ref,{'uri':location});return ref

    @staticmethod
    def validate_uri(uri):
        u=urlsplit(uri)
        if u.scheme!='https' or u.hostname!='www.googleapis.com' or u.username or u.password or u.port not in (None,443) or not u.path.startswith('/upload/youtube/') or u.fragment:
            raise ValueError('Unexpected upload-session destination')

    def resume(self,ref,path,spec):
        uri=self.vault.load(ref)['uri'];self.validate_uri(uri);total=spec['bytes']
        # Always ask server offset first, including after a lost final response.
        r=self.send('put',uri,data=b'',headers={'Content-Length':'0','Content-Range':f'bytes */{total}'},timeout=90,allow_redirects=False)
        if r.status_code in (404,410): raise yt.AmbiguousUpload()
        checked_response(r)
        if r.status_code in (200,201): return r.json()
        value=r.headers.get('Range','');m=re.fullmatch(r'bytes=0-(\d+)',value) if value else None
        if value and not m: raise ValueError('Invalid resumable upload offset')
        start=int(m[1])+1 if m else 0
        if not 0<=start<total or start%262144: raise ValueError('Unsafe resumable offset')
        with Path(path).open('rb') as stream:
            stream.seek(start);chunk=stream.read(self.chunk_size)
        end=start+len(chunk)-1
        r=self.send('put',uri,data=chunk,headers={'Content-Type':'video/mp4','Content-Length':str(len(chunk)),
            'Content-Range':f'bytes {start}-{end}/{total}'},timeout=90,allow_redirects=False)
        if r.status_code in (404,410): raise yt.AmbiguousUpload()
        checked_response(r)
        return r.json() if r.status_code in (200,201) else None

    def get_video(self,video_id):
        if not yt.VIDEO_ID.fullmatch(video_id or ''): raise ValueError('Invalid video ID')
        r=checked_response(self.send('get','https://www.googleapis.com/youtube/v3/videos',params={
          'part':'snippet,status,processingDetails','id':video_id},timeout=45,allow_redirects=False))
        items=r.json().get('items',[])
        if len(items)!=1: raise ValueError('Video unavailable to the authorized channel')
        return items[0]

    def schedule(self,video_id,status):
        if status.get('privacyStatus')!='private' or yt.timestamp(status.get('publishAt'))<time.time()+300:
            raise ValueError('Refuse public or past-time scheduling')
        checked_response(self.send('put','https://www.googleapis.com/youtube/v3/videos',params={'part':'status'},
            json={'id':video_id,'status':status},timeout=45,allow_redirects=False))

    def thumbnail(self,video_id,path):
        with Path(path).open('rb') as stream:
            checked_response(self.send('post','https://www.googleapis.com/upload/youtube/v3/thumbnails/set',
                params={'videoId':video_id,'uploadType':'media'},data=stream,headers={'Content-Type':'image/jpeg'},timeout=60,allow_redirects=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    c=s.add_parser('connect');c.add_argument('root');c.add_argument('client_json');c.add_argument('role',choices=f.CHANNELS);c.add_argument('confirmed_channel');c.add_argument('--write',action='store_true')
    for name in ('step','verify'):
        c=s.add_parser(name);c.add_argument('root');c.add_argument('batch')
    a=p.parse_args()
    try:
        if a.command=='connect': out=oauth_connect(a.root,a.client_json,a.role,a.confirmed_channel,a.write)
        else:
            yt.approve_live(a.root,a.batch);transport=OfficialTransport(a.root,a.batch)
            if a.command=='step':
                result=yt.tick(a.root,a.batch,transport);out={'id':result['id'],'state':result['state'],'items':[{'file':i['file'],'state':i['state'],'videoId':i['video_id']} for i in result['items']]}
            else: out=yt.refresh_verification(a.root,a.batch,transport)
        print(json.dumps(out,ensure_ascii=False,indent=2))
    except Exception as error:
        # Authentication library exceptions can contain sensitive request URLs.
        print(json.dumps({'ok':False,'error':str(error) if isinstance(error,ValueError) else type(error).__name__,'secretsOmitted':True},ensure_ascii=False));raise SystemExit(1)
