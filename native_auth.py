"""Local-only original login/registration flow. No email/SMS is sent."""
import re
import secrets
import time
from http.cookies import SimpleCookie
from server_errors import AuthError

def response(descriptors=None):
    return {"status":"SUCCESS","response_context":{"scenario_plan":{"blocker_descriptors":descriptors or []}}}

def descriptor(kind,data=None):return {"id":"sim_onboarding_"+kind,"blocker":{kind:data or {}}}

def dispatch(path,data,store,cookie_header):
    cookies=SimpleCookie(cookie_header or '')
    token=cookies['sandbox_login'].value if 'sandbox_login' in cookies else ''
    with store.connect() as db:flow=db.execute("SELECT * FROM login_flows WHERE token=? AND expires>?",(token,int(time.time()))).fetchone()
    flow=dict(flow) if flow else None
    if path in ('/2.0/cash/register-email','/2.0/cash/register-sms'):
        email=path.endswith('register-email');kind='EMAIL' if email else 'SMS'
        alias=data.get('email_address' if email else 'sms_number')
        valid=isinstance(alias,str) and (re.fullmatch(r'[A-Za-z0-9._+-]{1,60}@(example\.(com|net|org)|sandbox\.invalid)',alias) if email else re.fullmatch(r'\+120255501[0-9]{2}',alias))
        if not valid:raise AuthError(400,'Use an example.com email or a fictional +12025550100–0199 phone number')
        token='sim_login_'+secrets.token_urlsafe(24)
        with store.connect() as db:
            db.execute('DELETE FROM login_flows WHERE expires<?',(int(time.time()),))
            db.execute('INSERT INTO login_flows VALUES(?,?,?,?,?,?)',(token,alias,kind,None,'VERIFY',int(time.time())+900))
        result=response([descriptor('email_verification' if email else 'phone_verification',{'email':alias} if email else {'number':alias})]);result['token']=token
        return result,{'Set-Cookie':'sandbox_login='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=900'}
    if not flow:return None
    uid=flow['user_id'];stage=flow['stage'];headers={}
    if path in ('/2.0/cash/verify-email','/2.0/cash/verify-sms'):
        code=data.get('verification_code' if flow['kind']=='EMAIL' else 'sms_verification_code')
        alias=data.get('email_address' if flow['kind']=='EMAIL' else 'sms_number')
        if code!='123456':return {'status':'INVALID_VERIFICATION_CODE'},{}
        if alias!=flow['alias']:raise AuthError(400,'Verification alias does not match')
        if stage!='VERIFY':raise AuthError(409,'This login code is already used')
        uid=store.find_alias(flow['kind'],alias);fresh=uid is None
        if fresh:
            prefix=re.sub('[^a-z0-9_]','_',alias.split('@')[0].lower()) if flow['kind']=='EMAIL' else 'player_'+secrets.token_hex(3)
            if not re.fullmatch('[a-z][a-z0-9_]{2,23}',prefix):prefix='player_'+secrets.token_hex(4)
            with store.connect() as db:exists=db.execute('SELECT 1 FROM users WHERE username=?',(prefix,)).fetchone()
            if exists:prefix='player_'+secrets.token_hex(4)
            uid=store.register(prefix,secrets.token_urlsafe(32),'Sandbox player')['id']
            store.update_settings(uid,aliases=[{'type':flow['kind'],'canonical_text':alias,'verified':True}],onboarding_stage='NAME')
        next_stage=store.settings(uid).get('onboarding_stage') or 'COMPLETE'
        session,csrf,_=store.issue_session(uid)
        headers['Set-Cookie']='sandbox_session='+session+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400'
        with store.connect() as db:db.execute('UPDATE login_flows SET user_id=?,stage=? WHERE token=?',(uid,next_stage,token))
        result=response([descriptor('name' if next_stage=='NAME' else 'cashtag')] if next_stage!='COMPLETE' else []);result['token']=token
        return result,headers
    if uid and stage=='NAME' and path=='/2.0/cash/set-full-name':
        store.update_profile(uid,data.get('full_name'))
        store.update_settings(uid,onboarding_stage='CASHTAG')
        with store.connect() as db:db.execute("UPDATE login_flows SET stage='CASHTAG' WHERE token=?",(token,))
        return response([descriptor('cashtag')]),{}
    if uid and stage=='CASHTAG' and path=='/2.0/cash/set-cashtag':
        store.set_handle(uid,data.get('cashtag'))
        store.update_settings(uid,onboarding_stage=None)
        with store.connect() as db:db.execute("UPDATE login_flows SET stage='COMPLETE' WHERE token=?",(token,))
        return response(),{'Set-Cookie':'sandbox_login=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/'}
    return None
