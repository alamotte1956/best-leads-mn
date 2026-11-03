"""Fixed-origin Intuit OAuth/API transport. No redirects or implicit retries."""
import base64
import hashlib
import json
import os
import time
from urllib.parse import urlencode
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from cryptography.fernet import Fernet,InvalidToken

CALLBACK='https://www.restorationcontractorsmn.com/admin/quickbooks/callback'
AUTHORIZATION='https://appcenter.intuit.com/connect/oauth2'
TOKEN='https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer'
REVOKE='https://developer.api.intuit.com/v2/oauth2/tokens/revoke'
BASES={'sandbox':'https://sandbox-quickbooks.api.intuit.com','production':'https://quickbooks.api.intuit.com'}
class QBOError(Exception):pass
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def environment():
    value=os.environ.get('QBO_ENVIRONMENT','sandbox')
    if value not in BASES:raise QBOError('Choose sandbox or production in the protected QuickBooks configuration.')
    return value

def readiness():
    missing=[key for key in ('QBO_CLIENT_ID','QBO_CLIENT_SECRET','QBO_TOKEN_KEY') if not os.environ.get(key)]
    if os.environ.get('QBO_ENABLED','').lower()!='true':missing.append('QBO_ENABLED')
    try:environment()
    except QBOError:missing.append('QBO_ENVIRONMENT')
    if os.environ.get('QBO_TOKEN_KEY'):
        try:Fernet(os.environ['QBO_TOKEN_KEY'].encode())
        except (ValueError,TypeError):missing.append('valid QBO_TOKEN_KEY')
    return missing

def binding():
    return hashlib.sha256((environment()+'|'+os.environ.get('QBO_CLIENT_ID','')+'|'+CALLBACK).encode()).hexdigest()

def seal(data):
    try:return Fernet(os.environ['QBO_TOKEN_KEY'].encode()).encrypt(json.dumps(data).encode()).decode()
    except (KeyError,ValueError,TypeError):raise QBOError('QuickBooks token encryption is not configured correctly.') from None

def unseal(value):
    try:return json.loads(Fernet(os.environ['QBO_TOKEN_KEY'].encode()).decrypt(value.encode()))
    except (KeyError,ValueError,TypeError,InvalidToken):raise QBOError('Restore the configured token-encryption key or reconnect QuickBooks.') from None

def transport(url,method='GET',data=None,headers=None):
    payload=None if data is None else data
    req=Request(url,data=payload,method=method,headers={'Accept':'application/json',
        'User-Agent':'RestorationContractorsMN/1.0',**(headers or {})})
    try:
        with build_opener(NoRedirect()).open(req,timeout=20) as response:
            raw=response.read(2*1024*1024+1)
            if len(raw)>2*1024*1024:raise QBOError('QuickBooks returned too much data. Choose a shorter report period.')
            if not raw:return {}
            result=json.loads(raw)
            if not isinstance(result,dict) or result.get('Fault'):raise QBOError('QuickBooks rejected the request. Review the connection and account mapping.')
            return result
    except (HTTPError,URLError,TimeoutError,ValueError,OSError):
        # Provider bodies, authorization headers, codes and token values are never rendered/logged.
        raise QBOError('QuickBooks did not confirm the request. Check its status before retrying an accounting write.') from None

def token_request(fields):
    credential=base64.b64encode((os.environ['QBO_CLIENT_ID']+':'+os.environ['QBO_CLIENT_SECRET']).encode()).decode()
    return transport(TOKEN,'POST',urlencode(fields).encode(),{'Authorization':'Basic '+credential,'Content-Type':'application/x-www-form-urlencoded'})

def token_data(response):
    try:
        if not all(isinstance(response[k],str) and 1<=len(response[k])<=16384 for k in ('access_token','refresh_token')):raise ValueError()
        expires=int(response['expires_in']);refresh=int(response['x_refresh_token_expires_in'])
        if not 0<expires<=86400 or not 0<refresh<=366*86400:raise ValueError()
        return dict(access_token=response['access_token'],refresh_token=response['refresh_token'],
                    access_expires=time.time()+expires,refresh_expires=time.time()+refresh)
    except (KeyError,ValueError,TypeError):raise QBOError('Intuit returned an invalid token response. Restart the connection.') from None

def raw_api(mode,realm,token,path,params=None,payload=None):
    if mode not in BASES or not realm.isascii() or not realm.isdigit() or not path.startswith('/') or '..' in path:
        raise QBOError('Invalid QuickBooks company or API operation.')
    url=BASES[mode]+'/v3/company/'+realm+path
    if params:url+='?'+urlencode(params)
    return transport(url,'GET' if payload is None else 'POST',None if payload is None else json.dumps(payload).encode(),
        {'Authorization':'Bearer '+token,'Content-Type':'application/json'})

def api(connection_id,path,params=None,payload=None,expected_realm=None):
    from app import db,QuickBooksConnection
    from sqlalchemy import select
    connection=db.session.execute(select(QuickBooksConnection).where(QuickBooksConnection.id==connection_id).with_for_update().execution_options(populate_existing=True)).scalar_one()
    if (connection.environment!=environment() or connection.client_binding!=binding() or connection.status!='connected' or not connection.encrypted_tokens
            or (expected_realm is not None and connection.realm_id!=expected_realm)):
        db.session.rollback();raise QBOError('QuickBooks must be reconnected for this application and environment.')
    tokens=unseal(connection.encrypted_tokens)
    if tokens['access_expires']<=time.time()+60:
        if tokens['refresh_expires']<=time.time():
            connection.status='reauthorize';db.session.commit();raise QBOError('QuickBooks authorization expired. Reconnect the company.')
        try:tokens=token_data(token_request({'grant_type':'refresh_token','refresh_token':tokens['refresh_token']}))
        except QBOError:
            connection.status='reauthorize';db.session.commit();raise
        connection.encrypted_tokens=seal(tokens)
    mode,realm=connection.environment,connection.realm_id
    # Commit rotated credentials before any later API failure can cause rollback.
    db.session.commit()
    return raw_api(mode,realm,tokens['access_token'],path,params,payload)
