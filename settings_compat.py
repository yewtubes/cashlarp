"""Original settings controls backed by local roleplay data."""
from compat import CompatibilityError

def complete():return {"status":"SUCCESS","response_context":{"scenario_plan":{"blocker_descriptors":[]}}}
def block(kind,value,token=None,supplement=None):
    descriptor={"id":"sim_settings_"+kind,"blocker":{kind:value}}
    if supplement:descriptor["supplement"]={kind:supplement}
    result={"status":"SUCCESS","response_context":{"scenario_plan":{"blocker_descriptors":[descriptor]}}}
    if token:result["token"]=token
    return result

def dispatch(path,data,store,uid):
    cfg=store.settings(uid)
    if path=="/cash-app/notification-settings/api/web/notification-settings-sync-value":
        categories=["ACCOUNT_SECURITY","ACCOUNT_NOTICES","ACCOUNT_CHANGES","ACTIVITY_TRANSACTIONS","MARKETING_CASH_APP_NEWS","MARKETING_OFFERS","MARKETING_EXCLUSIVES","CASH_APP_TAXES"]
        saved=cfg.get("category_notifications",{})
        has_email=any(a["type"]=="EMAIL" for a in cfg["aliases"]);has_phone=any(a["type"]=="SMS" for a in cfg["aliases"])
        rows=[]
        for name in categories:
            category="NOTIFICATION_CATEGORY_"+name;previous=saved.get(category,{})
            rows.append({"account_token":uid,"category":category,"version":previous.get("version",1),
                         "email_channel_state":previous.get("email_channel_state","CLIENT_CHANNEL_STATE_SWITCHED_OFF_ENABLED") if has_email else "CLIENT_CHANNEL_STATE_UNAVAILABLE_NO_ALIASES",
                         "sms_channel_state":previous.get("sms_channel_state","CLIENT_CHANNEL_STATE_SWITCHED_OFF_ENABLED") if has_phone else "CLIENT_CHANNEL_STATE_UNAVAILABLE_NO_ALIASES"})
        return {"account_holder_token":uid,"notification_settings":{"category_preferences":rows},"render_data":{"sponsees_render_data":[]}}
    if path=="/cash-app/notification-settings/api/update-category-notification-settings":
        updates=data.get("updates")
        if not isinstance(updates,list) or len(updates)>20:raise CompatibilityError(400,"Invalid notification update")
        saved=cfg.get("category_notifications",{}).copy()
        states={"CLIENT_CHANNEL_STATE_SWITCHED_ON_ENABLED","CLIENT_CHANNEL_STATE_SWITCHED_OFF_ENABLED"}
        for update in updates:
            if not isinstance(update,dict) or update.get("account_token",uid)!=uid or not isinstance(update.get("category"),str):raise CompatibilityError(403,"Update only your local notification settings")
            category=update["category"]
            previous=saved.get(category,{}).copy()
            for channel in ("email_channel_state","sms_channel_state"):
                if channel in update:
                    if update[channel] not in states:raise CompatibilityError(400,"Invalid channel state")
                    previous[channel]=update[channel]
            previous["version"]=previous.get("version",1)+1;saved[category]=previous
        store.update_settings(uid,category_notifications=saved);return {"status":"SUCCESS"}
    if path=="/2.0/cash/set-notification-preference":
        preference=data.get("notification_preference",{});alias=preference.get("alias",{})
        if type(preference.get("enabled")) is not bool or not any(a["type"]==alias.get("type") and a["canonical_text"]==alias.get("canonical_text") for a in cfg["aliases"]):raise CompatibilityError(400,"Choose one of your local aliases")
        saved=cfg.get("contact_preferences",{}).copy();saved[alias["type"]+":"+alias["canonical_text"]]=preference["enabled"]
        store.update_settings(uid,contact_preferences=saved);return {"status":"SUCCESS"}
    if path=="/cash-app/security/1.0/get-account-settings":
        return {"require_passcode_confirmation":cfg["require_passcode_confirmation"],"has_passcode":cfg["has_passcode"]}
    if path=="/2.0/cash/set-incoming-request-policy":
        policy=data.get("incoming_request_policy")
        if policy not in ("ALLOW_ALL","ALLOW_CONTACTS","DENY_ALL"):raise CompatibilityError(400,"Invalid request policy")
        store.update_settings(uid,incoming_request_policy=policy);return {}
    if path in ("/2.0/cash/register-email","/2.0/cash/register-sms"):
        email=path.endswith("register-email");kind="EMAIL" if email else "SMS"
        alias=data.get("email_address" if email else "sms_number")
        token=store.begin_alias(uid,kind,alias)
        return block("email_verification" if email else "phone_verification",{"email":alias} if email else {"number":alias},token)
    if path in ("/2.0/cash/verify-email","/2.0/cash/verify-sms"):
        email=path.endswith("verify-email");code=data.get("verification_code" if email else "sms_verification_code")
        if code!="123456":return {"status":"INVALID_VERIFICATION_CODE"}
        store.verify_alias(uid,"EMAIL" if email else "SMS",data.get("email_address" if email else "sms_number"),code)
        return complete()
    if path=="/2.0/cash/unregister-alias":
        alias=data.get("alias")
        if not isinstance(alias,dict):raise CompatibilityError(400,"Choose a local alias")
        aliases=[a for a in cfg["aliases"] if (a["type"],a["canonical_text"])!=(alias.get("type"),alias.get("canonical_text"))]
        store.update_settings(uid,aliases=aliases);return complete()
    if path=="/2.0/cash/set-address":
        address=data.get("postal_address")
        allowed={"address_line_1","address_line_2","locality","administrative_district_level_1","postal_code","country_code"}
        if not isinstance(address,dict) or any(not isinstance(v,str) or len(v)>120 for v in address.values()):raise CompatibilityError(400,"Invalid local address")
        address={k:v for k,v in address.items() if k in allowed}
        if address.get("country_code","US")!="US":raise CompatibilityError(400,"This sandbox uses US address fields")
        store.update_settings(uid,postal_address=address);return complete()
    if path=="/2.0/cash/set-passcode":
        if cfg["has_passcode"] and not store.check_pin(uid,data.get("old_passcode")):return {"status":"INVALID_PASSCODE"}
        store.set_pin(uid,data.get("new_passcode"),data.get("old_passcode"));return complete()
    if path=="/2.0/cash/verify-passcode":
        token=data.get("_sandbox_flow_token")
        with store.connect() as db:flow=db.execute("SELECT purpose FROM activation_flows WHERE token=? AND user_id=? AND expires>strftime('%s','now')",(token,uid)).fetchone()
        if flow and flow["purpose"] in ("DISABLE_SECURITY","ENABLE_SECURITY"):
            if not store.check_pin(uid,data.get("passcode")):return {"status":"INVALID_PASSCODE"}
            store.update_settings(uid,require_passcode_confirmation=flow["purpose"]=="ENABLE_SECURITY");return complete()
    if path=="/2.0/cash/get-flow":
        initiation=data.get("initiation_data","")
        if not isinstance(initiation,str):raise CompatibilityError(400,"Flow name required")
        flow=initiation.split("?",1)[0]
        if flow=="SET_ADDRESS":return {**block("address",{"requires_street_address":True,"requires_city":True,"requires_state":True,"requires_postal_code":True},store.start_activation(uid,"ADDRESS"),{"address_prefill":cfg["postal_address"]}),"client_scenario":"PLASMA"}
        if flow in ("SET_OR_UPDATE_PASSCODE","ENABLE_SECURITY_LOCK_FOR_MOVE_MONEY","DISABLE_SECURITY_LOCK"):
            if flow=="SET_OR_UPDATE_PASSCODE" or not cfg["has_passcode"]:
                return {**block("passcode_creation",{"requires_existing_passcode":cfg["has_passcode"]},store.start_activation(uid,"SET_PIN")),"client_scenario":"PLASMA"}
            purpose="DISABLE_SECURITY" if flow=="DISABLE_SECURITY_LOCK" else "ENABLE_SECURITY"
            return {**block("passcode_verification",{"instrument":{"token":"CUSTOMER_PASSCODE"}},store.start_activation(uid,purpose),{"main_text":"Enter your local sandbox PIN"}),"client_scenario":"PLASMA"}
    return None
