"""Authenticated local account export; never includes authentication material."""
import base64
import json
import time

SETTINGS={'aliases','postal_address','incoming_request_policy','require_passcode_confirmation',
          'has_passcode','savings_goal_cents','round_ups_enabled','category_notifications','contact_preferences','notifications'}


def export(store, uid):
    with store.connect() as db:
        db.execute('BEGIN')
        account=db.execute('SELECT id,username,display_name,balance_cents,created_at FROM users WHERE id=?',(uid,)).fetchone()
        if not account:raise ValueError('Account not found')
        settings=db.execute('SELECT json FROM user_settings WHERE user_id=?',(uid,)).fetchone()
        settings=json.loads(settings['json']) if settings else {}
        savings=db.execute('SELECT balance_cents FROM savings_accounts WHERE user_id=?',(uid,)).fetchone()
        extras=db.execute('SELECT card_enabled,card_activated,btc_sats FROM extras WHERE user_id=?',(uid,)).fetchone()
        preferences=db.execute('SELECT cashtag,public_enabled FROM preferences WHERE user_id=?',(uid,)).fetchone()
        result={'format':'cashlarp-personal-data-v1','mode':'local_simulation','exported_at':int(time.time()),
                'account':dict(account),'settings':{k:v for k,v in settings.items() if k in SETTINGS},
                'savings_balance_cents':savings['balance_cents'] if savings else 0,
                'card_and_bitcoin':dict(extras) if extras else {},
                'public_profile':dict(preferences) if preferences else {}}
        queries={
            'payments':('SELECT * FROM transfers WHERE sender=? OR recipient=?',(uid,uid)),
            'requests':('SELECT * FROM requests WHERE requester=? OR payer=?',(uid,uid)),
            'cash_ledger':('SELECT * FROM ledger WHERE user_id=?',(uid,)),
            'cash_funding':('SELECT * FROM balance_changes WHERE user_id=?',(uid,)),
            'savings_transfers':('SELECT * FROM savings_transfers WHERE user_id=?',(uid,)),
            'bitcoin_trades':('SELECT * FROM trades WHERE user_id=?',(uid,)),
        }
        for name,(query,args) in queries.items():result[name]=[dict(row) for row in db.execute(query,args)]
        photo=db.execute('SELECT mime_type,image FROM profile_photos WHERE user_id=?',(uid,)).fetchone()
        result['profile_photo']={'mime_type':photo['mime_type'],'base64':base64.b64encode(photo['image']).decode()} if photo else None
        design=db.execute('SELECT theme,include_cashtag,image,touch_data FROM card_designs WHERE user_id=?',(uid,)).fetchone()
        result['card_design']={'theme':design['theme'],'include_cashtag':bool(design['include_cashtag']),
                               'image_base64':base64.b64encode(design['image']).decode(),'touch_data':json.loads(design['touch_data'])} if design else None
        return result
