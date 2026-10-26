"""Local state for server-driven journeys rendered by captured native controls."""
from decimal import Decimal
import re
from compat import CompatibilityError, success


def form(title, body, action, button, token, fields=None):
    elements=[{'id':'journey_title','text_element':{'text':title,'size':'LARGE'}},
              {'id':'journey_body','text_element':{'text':body}}]
    elements.extend(fields or [])
    return {'status':'SUCCESS','token':token,'client_scenario':'PLASMA',
            'response_context':{'scenario_plan':{'blocker_descriptors':[{'id':'sim_'+action,
              'blocker':{'form':{'elements':elements,'primary_action':{'text':button,'submit_action':{'id':action}}}}}]}}}


def dispatch(path,data,store,uid):
    cfg=store.settings(uid)
    if path=='/2.0/cash/get-flow':
        flow=data.get('initiation_data','').split('?',1)[0]
        if flow=='SET_SAVINGS_GOAL':
            return form('Savings goal','Enter a goal in dollars. Enter 0 to remove your goal.',
                        'sim_save_savings_goal','Save goal',store.start_activation(uid,'SAVINGS_GOAL'),
                        [{'id':'goal_amount','text_input_element':{'input_fields':[{'label_text':'Goal amount (USD)','keyboardType':'DECIMAL','validations':[{'regex':'[0-9]+([.][0-9]{1,2})?'}]}]}}])
        if flow=='PIGGYBANK_SAVINGS_ROUND_UP':
            enabled=bool(cfg.get('round_ups_enabled',False))
            return form('Round Ups','Round Ups are '+('on.' if enabled else 'off.')+' Eligible card purchases round up to the next dollar and save the difference. This local instance has no card-purchase network connected.',
                        'sim_roundups_off' if enabled else 'sim_roundups_on','Turn off Round Ups' if enabled else 'Enable Round Ups',store.start_activation(uid,'ROUNDUPS'))
    if path=='/2.0/cash/complete-scenario' and data.get('_sandbox_client_scenario')=='REPORT_LOST_CARD':
        return form('Replace your card','Your current card will be deactivated. Your replacement keeps your saved design.',
                    'sim_replace_card','Replace card',store.start_activation(uid,'REPLACE_CARD'))
    if path=='/2.0/cash/submit-form':
        action=data.get('action_id');token=data.get('_sandbox_flow_token')
        if action=='sim_save_savings_goal':
            results=data.get('results',[])
            if not isinstance(results,list):raise CompatibilityError(400,'Form results required')
            field=next((r for r in results if isinstance(r,dict) and r.get('id')=='goal_amount'),{})
            result=field.get('text_input_result',{})
            if not isinstance(result,dict):raise CompatibilityError(400,'Goal input required')
            values=result.get('input_field_values',[])
            if not isinstance(values,list):raise CompatibilityError(400,'Goal input required')
            value=values[0].strip() if values and isinstance(values[0],str) else ''
            if not re.fullmatch(r'(0|[1-9][0-9]{0,12})(\.[0-9]{1,2})?',value):raise CompatibilityError(400,'Enter a nonnegative dollar amount with at most two decimal places')
            cents=int(Decimal(value)*100)
            if cents>100_000_000_000_000:raise CompatibilityError(400,'Savings goal exceeds the local balance limit')
            store.apply_settings_flow(uid,token,'SAVINGS_GOAL',{'savings_goal_cents':cents or None})
            return success('Savings goal saved' if cents else 'Savings goal removed')
        if action in ('sim_roundups_on','sim_roundups_off'):
            store.apply_settings_flow(uid,token,'ROUNDUPS',{'round_ups_enabled':action=='sim_roundups_on'})
            return success('Round Ups preference saved')
        if action=='sim_replace_card':
            store.replace_card(uid,token)
            return success('Your replacement card is ready to activate')
    return None
