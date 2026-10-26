"""Compatibility responses for the unchanged account client; fictional data only."""
from datetime import datetime, timezone
import json
import csv
import io
import secrets
import re
from pathlib import Path
from copy import deepcopy
import hashlib

class CompatibilityError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message

def money(amount):
    return {"amount": amount, "currency_code": "USD"}

def dollars(cents):
    return "$" + format(cents // 100, ",") + "." + str(cents % 100).zfill(2)

def profile(user, extra=None, preferences=None, settings=None):
    result = {
        "customer_token":user["id"],"customer_since":user["created_at"]*1000,"country_code":"US","full_name":user["display_name"],
        "first_name":user["display_name"],"cashtag":user["username"],"default_currency":"USD",
        "email_address":user["username"]+"@example.com",
        "instruments":[{"token":"sim_balance_"+user["id"],"cash_instrument_type":"CASH_BALANCE",
                        "available_balance":money(user["balance_cents"]),"balance":money(user["balance_cents"]),"status":"VERIFIED"},{"token":"sim_funding_"+user["id"],"cash_instrument_type":"DEBIT_CARD",
                        "supports_cash_in":True,"supports_cash_out":True,"brand":"VISA","suffix":simulated_last_four(user["id"], "funding"),
                        "display_name":"Visa","status":"VERIFIED"}],
        "deposit_preference_data":{"cash_out_options":[{"deposit_preference":"TRANSFER_SLOWLY_WITHOUT_FEE","options_text":"Standard withdrawal (free)","fee_data":{"fee_bps":0}}]},
        "aliases":[],"is_business":False,"rate_plan":"PERSONAL","is_verified":True,
        "capabilities":[],"notifications":[],
    }
    if settings:
        result["photo_url"]=settings.get("photo_url", "")
        for key in ("aliases","postal_address","incoming_request_policy","has_passcode","require_passcode_confirmation"):
            result[key]=settings[key]
        result["notification_preferences"]=[{"alias":{"type":a["type"],"canonical_text":a["canonical_text"]},"enabled":settings.get("contact_preferences",{}).get(a["type"]+":"+a["canonical_text"],False)} for a in settings["aliases"]]
        result["aliases"]=[{"alias":{"type":a["type"],"canonical_text":a["canonical_text"]},"verified":a.get("verified",True),"display_date":0} for a in settings["aliases"]]
    if preferences:
        result["cashtag"]=preferences["cashtag"]
        result["cashtag_url"]="/sandbox/player/"+preferences["cashtag"]
        result["cashtag_url_enabled"]=bool(preferences["public_enabled"])
    if extra:
        result["issued_card"]=card(user,extra)
        result["instruments"].append({"token":"sim_btc_"+user["id"],"cash_instrument_type":"CASH_BALANCE","available_balance":{"amount":extra["btc_sats"],"currency_code":"BTC"}})
    return result

def simulated_last_four(uid, purpose="card"):
    return str(1000 + int(hashlib.sha256((purpose + ":" + uid).encode()).hexdigest()[:10], 16) % 9000)


def card(user,extra):
    return {"issued_at":user["created_at"],"activated":bool(extra.get("card_activated",0)),"card_order_data":{} if extra.get("card_activated") else {"state":"ISSUED"},"enabled":bool(extra["card_enabled"]),"virtual":False,
            "last_four":simulated_last_four(user["id"]),"cardholder_name":user["display_name"],
            "card_theme":extra.get("card_theme",{"id":"BLACK","card_color":"#000000","ink_color":"#ffffff"})}

_THEMES=json.loads((Path(__file__).parent/'capture/config/card-theme-configs.json').read_text())["card_themes"]
_THEMES += [json.loads(p.read_text()) for p in sorted((Path(__file__).parent/'local/card-themes').glob('*.json'))]
for _theme in _THEMES:
    _theme.setdefault("title",{"PINK_ID":"Pink","TORTOISE_ID":"Tortoise"}.get(_theme["id"],_theme["id"].removesuffix("_ID").replace("_"," ").title()))

def themes():
    return deepcopy(_THEMES)

def customization_descriptor():
    sections=[]
    for title,ids in [("Cashlarp",{"CASHLARP"}),("Classic",{"BLACK","WHITE","PINK_ID","GLOW_ID"}),("Signature",{"HOLO_ID","MOOD_ID","GLITTER_ID","TORTOISE_ID"}),("Metal",{"METAL_BLACK_ID","METAL_OIL_SLICK_ID"})]:
        options=[{"external_identifier":"sim_"+theme["id"].lower(),"accessibility_text":theme["title"]+" card",
                  "title":theme["title"],"detail_text":"Cashlarp card","card_availability":"AVAILABLE","customization_eligible":True,
                  "cashtag_display":"OPTIONAL","card_theme":theme,"card_preview_text":{"body":"Design your card",
                  "customize_card_button_title":"Customize","edit_customization_button_title":"Edit design"}} for theme in themes() if theme["id"] in ids]
        sections.append({"header_text":title,"short_title_text":title,"options":options})
    return {"id":"card_customization","blocker":{"card_customization":{"card_option_sections":sections}}}

def success(text, token=None):
    return {"status":"SUCCESS","response_context":{
        "payments":[{"token":token}] if token else [],"scenario_plan":{"blocker_descriptors":[]},
        "status_result":{"action":"SHOW_DIALOG","icon":"SUCCESS","text":text,
                         "primary_button":{"text":"Done","action":"PAY_SCREEN"}}}}

def payment_row(store, uid, item, request=False):
    if request:
        sender,recipient = item["payer"],item["requester"]
        counterpart = item["requester_username"] if uid == sender else item["payer_username"]
        status = item["status"]
        state = "WAITING_ON_SENDER" if status == "pending" else "COMPLETE" if status == "paid" else "CANCELED"
        label = "Request " + status
    else:
        sender,recipient = item["sender"],item["recipient"]
        counterpart = item["recipient_name"] if uid == sender else item["sender_name"]
        status,state,label = "paid","COMPLETE","Completed"
    pending = request and status == "pending"
    sent = uid == sender
    formatted = dollars(item["amount_cents"])
    history = {
        "title":counterpart,"primary_label":counterpart,"secondary_label":"" + (label if request else item["note"]),
        "tertiary_label":datetime.fromtimestamp(item["created_at"],timezone.utc).strftime("%b %d"),
        "amount_formatted_activity_list":("−" if sent else "+")+formatted,
        "amount_formatted":formatted,"amount_treatment":"STANDARD",
        "header_text":counterpart,"header_subtext":"Cashlarp",
        "details_view_content":{"rows":[item["note"] or "Simulated payment"]},
        "more_info_sheet_status_text":label,"more_info_sheet_header_icon":"WAITING" if pending else "CHECKMARK",
        "detail_rows":[{"label":"Status","value":label,"treatment":"BOLD"},
                       {"label":"Date","value":datetime.fromtimestamp(item["created_at"],timezone.utc).strftime("%b %d, %Y · %H:%M UTC")},
                       {"label":"Reference","value":item["id"]}],
        "footer_text":"Cashlarp · Simulated transaction.",
        "activity_section":"OUTSTANDING" if pending else "COMPLETED","is_outstanding_request":pending,"overflow_buttons":[],
    }
    if pending:
        if sent:
            history["overflow_buttons"] = [{"text":"Pay","action":"CONFIRM"},{"text":"Decline request","action":"CANCEL"}]
            history["inline_button"] = {"text":"Pay","action":"CONFIRM"}
            history["scenario_plan"] = {"blocker_descriptors":[{
                "id":"sim_confirm_request","blocker":{"confirm":{"explicit_confirmation":True,"initiated_by_recipient":False}},
                "supplement":{"confirm":{"main_text":"Pay " + formatted + "?"}}
            }]}
        else:
            history["overflow_buttons"] = [{"text":"Cancel request","action":"CANCEL"}]
    return {"row_id":item["id"],"display_date_epoch_ms":item["created_at"]*1000,
            "activity_row_section":"PENDING" if pending else "COMPLETE",
            "payment_history_inputs_row":{"entity_id":item["id"],"domain_type":"P2P",
                "payment":{"token":item["id"],"orientation":"BILL" if request else "CASH",
                           "role":"SENDER" if sent else "RECIPIENT","state":state,
                           "sender_id":sender,"recipient_id":recipient,"amount":money(item["amount_cents"]),"display_category":"ADC_P2P","history_data":history}}}

def activity_rows(store, uid, query="", savings=False):
    if not isinstance(query,str):
        raise CompatibilityError(400,"Search text required")
    rows=[]
    for transfer in store.activity(uid):
        receipt = store.receipt(uid,transfer["id"])
        rows.append(payment_row(store,uid,receipt))
    for request in store.requests(uid):
        if request["status"] != "paid":
            rows.append(payment_row(store,uid,request,True))
    for event in store.financial_events(uid):
        sent=event["delta"]<0
        item={"id":event["id"],"sender":uid if sent else "sim_play_money_source","recipient":"sim_play_money_sink" if sent else uid,
              "sender_name":event["label"],"recipient_name":event["label"],"note":event["label"],
              "amount_cents":abs(event["delta"]),"created_at":event["created_at"]}
        row=payment_row(store,uid,item)
        row["payment_history_inputs_row"]["payment"]["display_category"]=event["category"]
        rows.append(row)
    if savings:
        rows=[row for row in rows if row["row_id"].startswith("sim_savings_transfer_")]
        for row in rows:
            payment=row["payment_history_inputs_row"]["payment"]
            incoming=payment["role"]=="SENDER"
            payment["role"]="RECIPIENT" if incoming else "SENDER"
            payment["sender_id"]="sim_cash_"+uid if incoming else uid
            payment["recipient_id"]=uid if incoming else "sim_cash_"+uid
            payment["history_data"]["amount_formatted_activity_list"]=("+" if incoming else "−")+dollars(payment["amount"]["amount"])
    rows.sort(key=lambda r:(r["display_date_epoch_ms"],r["row_id"]),reverse=True)
    if query:
        normalized=query.lower().replace(",","").replace("$","")
        with store.connect() as db:names={r["id"]:r["username"] for r in db.execute("SELECT id,username FROM users")}
        def text(row):
            payment=row["payment_history_inputs_row"]["payment"];h=payment["history_data"]
            return " ".join([h["primary_label"],h["secondary_label"],h["amount_formatted"],names.get(payment["sender_id"],""),names.get(payment["recipient_id"],"")]).lower().replace(",","").replace("$","")
        rows=[r for r in rows if normalized in text(r)]
    return rows

def native_amount(data):
    amount=data.get("amount")
    if not isinstance(amount,dict) or amount.get("currency_code") != "USD":
        raise CompatibilityError(400,"Use fictional USD only")
    cents=amount.get("amount")
    if isinstance(cents,str) and re.fullmatch(r"[0-9]{1,15}",cents):
        cents=int(cents)
    return cents

def read_rpc(path, data, store, uid):
    if path == "/2.0/cash/get-flow" and not data.get("initiation_data") and isinstance(data.get("flow_type"), str):
        data = {**data, "initiation_data": data["flow_type"]}
    if path=="/2.0/cash/verify-passcode":
        pending=store.pending_action(uid,data.get("_sandbox_flow_token"))
        if pending:
            if not store.check_pin(uid,data.get("passcode")):return {"status":"INVALID_PASSCODE"}
            if pending["result"]:return json.loads(pending["result"])
            body=json.loads(pending["body"]);body["_sandbox_pin_authorized"]=True
            result=read_rpc(pending["path"],body,store,uid)
            store.finish_action(uid,pending["token"],result)
            return result
    from settings_compat import dispatch
    setting_result=dispatch(path,data,store,uid)
    if setting_result is not None:return setting_result
    user=store.user(uid)
    config=store.settings(uid)
    config["photo_url"]=store.profile_photo_url(uid)
    if path == "/2.0/cash/set-profile-photo":
        return {"image_url":store.set_profile_photo(uid,data.get("image_data"),data.get("mime_type"))}
    if path == "/2.0/cash/clear-profile-photo":
        with store.connect() as db:db.execute("DELETE FROM profile_photos WHERE user_id=?",(uid,))
        return {"image_url":""}
    extra=store.extras(uid)
    preferences=store.preferences(uid)
    needs_pin=path in ("/cash-app/internal-transfers/v1.0/add-cash","/cash-app/internal-transfers/v1.0/move-cash","/cash-app/cash-in/v1.0/add-cash","/cash-app/out/v1.0/initiate-cash-out","/cash-app/crypto/invest/exchange","/2.0/cash/confirm-payment") or (path=="/2.0/cash/initiate-payment" and data.get("orientation")=="CASH")
    if needs_pin and config["require_passcode_confirmation"] and not data.get("_sandbox_pin_authorized"):
        token=store.start_action(uid,path,data)
        descriptor={"id":"sim_authorize_action","blocker":{"passcode_verification":{"instrument":{"token":"CUSTOMER_PASSCODE"}}},"supplement":{"passcode_verification":{"main_text":"Confirm with your Cash PIN"}}}
        return {"status":"SUCCESS","token":token,"response_context":{"scenario_plan":{"blocker_descriptors":[descriptor]}}}
    design=store.card_design(uid)
    with store.connect() as db:
        has_design=db.execute("SELECT 1 FROM card_designs WHERE user_id=?",(uid,)).fetchone() is not None
    extra["card_theme"]=next(t for t in themes() if t["id"]==design["theme"])
    if path == "/cash-app/security/1.0/get-webauthn-credentials":
        return {"credentials":[]}
    if path == "/2.0/cash/get-cashtag-status":
        candidate=data.get("cashtag_candidate")
        status=store.handle_status(uid,candidate)
        return {"cashtag_candidate":candidate,"cashtag_status":status,"confirm_message":"Local sandbox cashtag","failure_message":"Choose an available lowercase sandbox cashtag (3–24 characters)"}
    if path == "/2.0/cash/set-cashtag":
        store.set_handle(uid,data.get("cashtag"))
        return {"status":"SUCCESS","response_context":{"scenario_plan":{"blocker_descriptors":[]}}}
    if path == "/2.0/cash/set-cashtag-url-enabled":
        store.set_public(uid,data.get("enabled"))
        return {}
    if path == "/2.0/cash/investing/get-investment-statements":
        return {"documents":[]}
    if path == "/cash-app/crypto/invest/get-crypto-tax-statements-external":
        return {"tax_documents":[]}
    if path == "/cash-app/activity-export/v1.0/create-export":
        rows=read_rpc("/cash-app/activity/v1.0/search",{"request":data},store,uid)["activity_rows"]
        output=io.StringIO();writer=csv.writer(output)
        writer.writerow(["CASHLARP — SIMULATED TRANSACTIONS"])
        writer.writerow(["reference","unix_milliseconds","player","description","fictional_amount"])
        for row in rows:
            h=row["payment_history_inputs_row"]["payment"]["history_data"]
            values=[row["row_id"],row["display_date_epoch_ms"],h["primary_label"],h["secondary_label"],h["amount_formatted_activity_list"]]
            writer.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(("=","+","-","@")) else v for v in values])
        rid="sim_export_"+secrets.token_hex(12)
        with store.connect() as db:db.execute("INSERT INTO exports VALUES(?,?,?)",(rid,uid,output.getvalue()))
        return {"request_id":rid}
    if path in ("/cash-app/activity-export/v1.0/get-export","/cash-app/activity-export/v1.0/download-export"):
        rid=data.get("request_id")
        if not isinstance(rid,str):raise CompatibilityError(400,"Export reference required")
        with store.connect() as db:row=db.execute("SELECT csv_text FROM exports WHERE id=? AND user_id=?",(rid,uid)).fetchone()
        if not row:raise CompatibilityError(404,"Sandbox export not found")
        if path.endswith("download-export"):return row["csv_text"]
        return {"status":"COMPLETE","progress_percentage":100}
    if path in ("/2.0/cash/get-display-name-status-client", "/cash-app/community/get-display-name-status"):
        return {"remaining_limit":1000}
    if path == "/2.0/cash/set-full-name":
        store.update_profile(uid,data.get("full_name"))
        return success("Sandbox display name updated")
    if path == "/2.0/cash/get-profile":
        return {"profile":profile(user,extra,preferences,config)}
    if path == "/2.0/cash/web/profile":
        return {"profile":profile(user,extra,preferences,config),"issued_cash_card":card(user,extra),"bitcoin_balance":{"snapshot":{"amount":extra["btc_sats"]}},"investing_portfolio_summary":{"has_portfolio":False}}
    if path == "/cash-app/savings/get-savings-overview":
        savings=money(store.savings_balance(uid))
        return {"customer":{"customer_status":"SAVINGS_CUSTOMER_STATUS_ADOPTED"},
                "balance":{"amount":savings,"stored_value_balance_token":"sim_savings_"+uid},
                "interest_rate":{"apy_rate":0,"interest_yield_status":"INTEREST_YIELD_STATUS_MANUALLY_DISABLED","interest_tiers_apy_rates":{"standard_interest_apy_rate":0,"enhanced_interest_apy_rate":0}},
                "versioned_savings_folders":{"v2_folders":[{"token":"sim_savings_"+uid,"balance":savings,"general_folder":{}}]},
                "config":{"max_number_of_goals":1,"savings_copy":{"default_savings_folder_label":"Savings","goal_complete_text":"Goal met!"}},
                "automation_section":{"title":"Save automatically","references":[]}}
    if path == "/cash-app/business-accounts/get-c4b-eligibility":
        return {"money_taxes_applet":{"is_eligible":False},"money_btc_applet":{"is_eligible":False}}
    if path == "/2.0/cash/get-historical-exchange-data":
        return {"price_history":{"price_ticks":[{"price_cents":10000000,"time":1700000000},{"price_cents":10000000,"time":1800000000}]}}
    if path in ("/2.0/cash/get-or-create-savings-balance", "/cash-app/savings/get-or-create-savings-balance"):
        return {"balance":{"amount":money(store.savings_balance(uid)),"stored_value_balance_token":"sim_savings_"+uid},"status":"ADOPTED"}
    if path in ("/2.0/cash/compute-disclosure-sync-value","/cash-app/banking-tab/v1/compute-disclosure-sync-value"):
        return {"sync_value":"sandbox","response_context":{"sync_entities_data":{"entities":[{"sync_value":{"fdic_insurance_customer_status":{}}}]}}}
    if path == "/2.0/cash/suggested-recipients":
        with store.connect() as db:
            users=db.execute("SELECT id,username,display_name FROM users WHERE id!=? ORDER BY username",(uid,)).fetchall()
        return {"suggested_recipients":[{"id":u["id"],"full_name":u["display_name"],"cashtag":store.preferences(u["id"])["cashtag"],"country_code":"US","email":u["username"]+"@example.com","is_business":False,"profile_photo_url":store.profile_photo_url(u["id"])} for u in users]}
    if path == "/cash-app/cash-in/v1.0/enqueue-cash-in-requirements":
        return {}
    if path == "/cash-app/banking-statements/statements/list":
        return {"statements":[]}
    if path == "/cash-app/banking-statements/types/list":
        return {"statement_type_details":[]}
    if path == "/cash-app/investing/get-customer-news":
        return {"bitcoin":{"news":[]}}
    if path == "/2.0/cash/investing/get-current-prices":
        return {"prices":[{"currency_code":"BTC","price":{"amount":10000000,"currency_code":"USD"}}]}
    if path in ("/cash-app/internal-transfers/v1.0/add-cash","/cash-app/internal-transfers/v1.0/move-cash"):
        snapshot=data.get("main_cash_balance_snapshot")
        if data.get("savings_balance_token") != "sim_savings_"+uid or not isinstance(snapshot,dict) or snapshot.get("instrument_token") != "sim_balance_"+uid:
            raise CompatibilityError(400,"Choose your own Cash and Savings balances")
        context=data.get("transfer_context")
        if context not in ({"home":{}},{"general_folder":{}}):
            raise CompatibilityError(400,"Choose your general Savings balance")
        direction="in" if path.endswith("/add-cash") else "out"
        if direction=="out" and data.get("target_cash_balance_token") != "sim_balance_"+uid:
            raise CompatibilityError(400,"Choose your own Cash balance")
        store.transfer_savings(uid,native_amount(data),direction,data.get("external_id"))
        return success("Moved "+dollars(native_amount(data))+(" to Savings" if direction=="in" else " to Cash"))
    if path == "/2.0/cash/set-card-customization":
        token=data.get("card_theme_token")
        selected=next((t for t in themes() if token in (t["token"],"sim_theme_"+t["id"])),None)
        if not selected:raise CompatibilityError(400,"Unknown local card theme")
        store.save_card_design(uid,selected["id"],data.get("image_bytes"),data.get("include_cashtag",False),data.get("touch_data",{}))
        return {"status":"SUCCESS","response_context":{"scenario_plan":{"blocker_descriptors":[]}}}
    if path == "/2.0/cash/verify-passcode":
        if not store.unlock_card(uid,data.get("_sandbox_flow_token"),data.get("passcode")):
            return {"status":"INVALID_PASSCODE"}
        return {"status":"SUCCESS","response_context":{"scenario_plan":{"blocker_descriptors":[]}}}
    if path == "/2.0/cash/submit-form":
        if data.get("action_id")!="sim_activate_card":raise CompatibilityError(501,"Form not connected locally")
        results=data.get("results",[])
        field=next((r for r in results if isinstance(r,dict) and r.get("id")=="sandbox_activation_code"),{})
        values=field.get("text_input_result",{}).get("input_field_values",[])
        store.activate_card(uid,data.get("_sandbox_flow_token"),values[0] if values else None)
        return success("Your card is activated.")
    if path == "/2.0/cash/get-flow":
        flow=data.get("initiation_data")
        if isinstance(flow,str) and flow.split("?",1)[0] in ("CHANGE_CARD_DESIGN","REQUEST_PHYSICAL_CARD"):
            return {"token":store.start_activation(uid,"DESIGN"),"client_scenario":"PLASMA","response_context":{"scenario_plan":{"blocker_descriptors":[customization_descriptor()]}}}
        if isinstance(flow,str) and flow.split("?",1)[0]=="ACTIVATE_PHYSICAL_CARD":
            token=store.start_activation(uid)
            descriptor={"id":"sim_card_activation","blocker":{"form":{"elements":[
                {"id":"activation_title","text_element":{"text":"Activate your card","size":"LARGE"}},
                {"id":"sandbox_activation_code","text_input_element":{"input_fields":[{"label_text":"Activation code","hint_text":"Use 123456 for this fictional card","keyboardType":"NUMBER_PAD","validations":[{"regex":"[0-9]{6}"}]}]}}
            ],"primary_action":{"text":"Activate","submit_action":{"id":"sim_activate_card"}}}}}
            return {"token":token,"client_scenario":"PLASMA","response_context":{"scenario_plan":{"blocker_descriptors":[descriptor]}}}
        if flow not in ("ENABLE_ISSUED_CARD","DISABLE_ISSUED_CARD_IN_POSTCARD"):
            raise CompatibilityError(501,"This journey is not connected locally")
        if flow=="ENABLE_ISSUED_CARD":
            token=store.start_activation(uid,"UNLOCK")
            descriptor={"id":"sim_card_unlock_pin","blocker":{"passcode_verification":{"instrument":{"token":"CUSTOMER_PASSCODE"}}},"supplement":{"passcode_verification":{"main_text":("Enter your Cash PIN to unlock your card" if config.get("pin_hash") else "Enter your Cash PIN to unlock your card")}}}
            return {"token":token,"client_scenario":"PLASMA","response_context":{"scenario_plan":{"blocker_descriptors":[descriptor]}}}
        store.set_card(uid,False)
        return {"token":"sim_card_flow_"+uid,"client_scenario":"PLASMA","response_context":{"scenario_plan":{"blocker_descriptors":[]}}}
    if path == "/cash-app/syncentitygateway/v1/batch-topic-sync":
        return {"successful_responses":[{"topic":42,"entities":[{"sync_value":{"scheme":{"modules":[{"hero_issued_card":{"card_rendering_info":{"card_theme":card(user,extra)["card_theme"],"customization_image_path":"/local-card-design/"+uid+".png" if has_design else ""}}}]}}}]}],"failed_requests":[]}
    if path == "/cash-app/crypto/invest/exchange":
        buy=data.get("source_currency")=="USD" and data.get("target_currency")=="BTC"
        sell=data.get("source_currency")=="BTC" and data.get("target_currency")=="USD"
        if not (buy or sell):
            raise CompatibilityError(400,"Only fictional USD / BTC exchange is available")
        source="sim_balance_"+uid if buy else "sim_btc_"+uid
        target="sim_btc_"+uid if buy else "sim_balance_"+uid
        if data.get("source_instrument_token")!=source or data.get("target_instrument_token")!=target:
            raise CompatibilityError(400,"Choose your own local balances")
        amount=data.get("source_amount" if buy else "target_amount")
        if sell and data.get("all_source_amount") is True:
            with store.connect() as db:
                previous=db.execute("SELECT cents FROM trades WHERE user_id=? AND idempotency_key=?",(uid,data.get("external_id"))).fetchone()
            amount=previous["cents"] if previous else extra["btc_sats"]//10
        if isinstance(amount,str) and re.fullmatch(r"[0-9]{1,15}",amount):amount=int(amount)
        store.exchange(uid,amount,buy,data.get("external_id"))
        return success(("Bought" if buy else "Sold")+" fictional Bitcoin at the fixed sandbox price of $100,000/BTC")
    if path == "/cash-app/cash-in/v1.0/add-cash":
        source,target=data.get("source"),data.get("target")
        if (not isinstance(source,dict) or source.get("token") != "sim_funding_"+uid
                or not isinstance(target,dict) or target.get("token") != "sim_balance_"+uid):
            raise CompatibilityError(400,"Choose your Cashlarp source and balance")
        result,_=store.change_balance(uid,native_amount(data),"add",data.get("external_id"))
        return success("Added " + dollars(result["amount_cents"]) + "")
    if path == "/cash-app/out/v1.0/initiate-cash-out":
        source=data.get("source")
        if (not isinstance(source,dict) or source.get("token") != "sim_balance_"+uid
                or data.get("deposit_preference") != "TRANSFER_SLOWLY_WITHOUT_FEE"):
            raise CompatibilityError(400,"Choose your Cashlarp balance")
        result,_=store.change_balance(uid,native_amount(data),"withdraw",data.get("external_id"))
        return success("Removed " + dollars(result["amount_cents"]) + "")
    if path == "/2.0/cash/initiate-payment":
        getters=data.get("payment_getters")
        orientation=data.get("orientation")
        if (not isinstance(getters,list) or len(getters)!=1 or not isinstance(getters[0],dict)
                or not isinstance(getters[0].get("id"),str) or orientation not in ("CASH","BILL")):
            raise CompatibilityError(400,"Choose one local sandbox user")
        if orientation == "CASH" and (not isinstance(data.get("instrument_selection"),dict)
                or data["instrument_selection"].get("instrument_token") != "sim_balance_"+uid):
            raise CompatibilityError(400,"Choose your Cashlarp balance")
        with store.connect() as db:
            recipient=db.execute("SELECT username,display_name FROM users WHERE id=?",(getters[0]["id"],)).fetchone()
        if not recipient:
            raise CompatibilityError(404,"Sandbox recipient not found")
        cents=native_amount(data)
        if orientation == "BILL":
            payment,_=store.create_request(uid,recipient["username"],cents,data.get("note",""),data.get("external_id"))
            return success("Requested " + dollars(payment["amount_cents"]) + " from " + recipient["display_name"],payment["id"])
        payment,_=store.transfer(uid,recipient["username"],cents,data.get("note",""),data.get("external_id"))
        return success("Sent " + dollars(payment["amount_cents"]) + " to " + recipient["display_name"],payment["id"])
    if path == "/2.0/cash/confirm-payment":
        tokens=data.get("payment_tokens")
        if not isinstance(tokens,list) or len(tokens)!=1 or not isinstance(tokens[0],str):
            raise CompatibilityError(400,"Choose one local request")
        result=store.resolve_request(uid,tokens[0],"pay")
        return success("Paid " + dollars(result["amount_cents"]) + "",result["transfer_id"])
    if path == "/2.0/cash/cancel-payment":
        rid=data.get("payment_token")
        request=next((r for r in store.requests(uid) if r["id"]==rid),None)
        if not request:
            raise CompatibilityError(404,"Sandbox request not found")
        action="cancel" if request["requester"]==uid else "decline"
        store.resolve_request(uid,rid,action)
        return success("Play-money request " + ("cancelled" if action=="cancel" else "declined"),rid)
    if path in ("/cash-app/activity/v1.0/page","/cash-app/activity/v1.0/search"):
        request=data.get("request",data)
        if not isinstance(request,dict):raise CompatibilityError(400,"Invalid activity search")
        token=request.get("activity_token",{})
        if not isinstance(token,dict):raise CompatibilityError(400,"Invalid activity token")
        savings=token.get("activity_token_type") in ("CUSTOMER_TOKEN_SAVINGS_ACCOUNT","SAVINGS_FOLDER_TOKEN")
        if savings and token.get("sub_token") not in (None,"sim_savings_"+uid):raise CompatibilityError(404,"Savings folder not found")
        rows=activity_rows(store,uid,request.get("free_text_search",""),savings=savings)
        def matches(row, f):
            payment=row["payment_history_inputs_row"]["payment"]
            if "counterparty" in f:
                cp=f["counterparty"]
                return (payment["recipient_id"] if cp.get("type")=="RECIPIENT" else payment["sender_id"]) == uid
            if "display_category_any_of" in f:
                return payment.get("display_category","ADC_P2P") in f["display_category_any_of"].get("display_categories",[])
            for field in ("amount","date"):
                if field in f:
                    entry=f[field]
                    value=payment["amount"]["amount"] if field=="amount" else row["display_date_epoch_ms"]
                    target=entry.get("amount" if field=="amount" else "date_in_epoch_millis")
                    if not isinstance(target,(int,float)):return False
                    return value <= target if entry.get("comparison")=="LESS_THAN_OR_EQUAL_TO" else value >= target
            return True
        groups=request.get("filter_groups",[])
        if isinstance(groups,list):
            for group in groups:
                if isinstance(group,dict):
                    for f in group.get("filters",[]):
                        if isinstance(f,dict):rows=[r for r in rows if matches(r,f)]
        sort=request.get("sort",{})
        if isinstance(sort,dict) and sort:
            if sort.get("sort_by_field")=="AMOUNT":
                rows.sort(key=lambda r:r["payment_history_inputs_row"]["payment"]["amount"]["amount"],reverse=sort.get("order")!="ASC")
            else:rows.sort(key=lambda r:r["display_date_epoch_ms"],reverse=sort.get("order")!="ASC")
        return {"activity_rows":rows,"has_more":False}
    if path == "/cash-app/activity/v1.0/get":
        global_id=data.get("activityItemGlobalId")
        rid=global_id.get("activity_row_id") if isinstance(global_id,dict) else None
        token=data.get("activity_token",{})
        savings=isinstance(token,dict) and token.get("activity_token_type") in ("CUSTOMER_TOKEN_SAVINGS_ACCOUNT","SAVINGS_FOLDER_TOKEN")
        row=next((r for r in activity_rows(store,uid,savings=savings) if r["row_id"]==rid),None)
        if not row and not savings:
            request=next((r for r in store.requests(uid) if r["id"]==rid),None)
            if request:
                row=payment_row(store,uid,request,True)
        if not row:
            raise CompatibilityError(404,"Sandbox activity not found")
        return {"activityRow":row}
    if path in ("/2.0/cash/cdp-track-event","/2.0/cash/record-completed-journey","/2.0/cash/record-completed-journey-batch",
                "/2.0/cash/set-locale-preference","/2.0/cash/set-onboarding-context","/cash-app/user-journeys/record-completed-journey"):
        return {}
    return None
