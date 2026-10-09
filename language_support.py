"""Native English templates; canonical task/slot identifiers stay language-neutral."""
import json
import re
from datetime import timedelta
import catalogue as C

EN_SYS = {
 'intent':'Identify the business domain, intent and explicitly stated slots in the user message. Return only JSON: {"domain":"domain","intent":"intent","slots":{"slot":"value"}}.',
 'slots':'Extract only explicitly stated slot values from the user message. Do not infer missing values. Return only JSON: {"slots":{"slot":"value"}}.',
 'domain':'Classify the business domain of the user message. Return only JSON: {"domain":"domain"}.',
 'dst_user':'Track the latest user state from the dialogue. Return only a JSON array of {"domain":"domain","slot":"slot","value":"value","active":true/false}. Keep withdrawn entries inactive.',
 'dst_belief':'Track the current active belief state from the dialogue. Return only a JSON object mapping "domain-slot" to the latest value. Exclude withdrawn entries.',
 'clarify':'Ask a specific clarification question for the listed missing information. Do not ask again for information already given. Return only the question.',
 'ecom':'You are an e-commerce after-sales assistant. Use dialogue history and tool results to choose the next action or reply. Tools: query_order_status, check_return_policy, create_after_sales_request. For a tool call return two lines: Action: tool_name\nAction Input: {"parameter":"value"}.',
}

ACTION_ROWS = {
 'order': ['check my order status','cancel my order','update my order details','request faster dispatch','confirm receipt of my order'],
 'logistics':['track my shipment','request faster delivery','investigate a shipment problem','change the delivery address'],
 'after_sales':['request a return and refund','request an exchange','request a repair','check my after-sales request','cancel my after-sales request'],
 'refund':['check my refund status','request a refund without returning the item','follow up on a delayed refund'],
 'invoice':['request an invoice','update an invoice','check an invoice'],
 'coupon':['check coupon conditions','claim a coupon','investigate a coupon redemption problem'],
 'product':['ask about a product','check product availability','check a product price'],
 'payment':['investigate a failed payment','check available payment methods','ask about installment payments'],
 'member':['check membership benefits','redeem membership points'],
 'complaint':['file a complaint'], 'account':['update my account details','investigate an account problem'],
 'bank_account':['check my account balance','check my account transactions'],
 'bank_card':['report a lost bank card','check my bank card status'],
 'transfer':['check my transfer status','check my transfer limit'],
 'loan':['check my repayment schedule','ask about early repayment'],
 'deposit':['check my deposit maturity date'], 'wealth':['check my investment redemption status'],
 'insurance':['check my insurance policy status','check my insurance claim status'],
 'flight':['search for a flight','request a flight ticket refund'],
 'train':['change my train ticket','search for a train ticket'],
 'hotel':['check hotel room options','cancel my hotel booking'],
 'ride':['check my ride order','file a ride complaint'],
 'mobile_plan':['check my mobile plan','change my mobile plan'],
 'mobile_bill':['check my mobile bill','dispute an unexpected mobile charge'],
 'broadband':['report a broadband fault','check my broadband installation'],
 'mobile_number':['report a lost mobile number'], 'course':['ask about course content','check a course price'],
 'enrollment':['check my course enrollment','cancel my course enrollment'],
 'class_schedule':['check my class schedule','reschedule a class'],
 'learning_account':['investigate a learning account login problem'],
}
EN_ACTIONS = {}
for domain, actions in ACTION_ROWS.items():
    scenes = [s for s in C.SCENARIOS if s['domain'] == domain]
    if len(scenes) != len(actions): raise RuntimeError('English action catalogue does not match scenarios')
    EN_ACTIONS.update({s['id']: a for s,a in zip(scenes,actions)})

EN_SLOT_LABELS = {k: k.replace('_',' ') for k in C.SLOT_LABELS}
EN_SLOT_LABELS.update(order_id='order ID', account_no='masked account', card_no='masked card',
                      tracking_no='tracking number', tax_no='tax ID', service_id='service ID',
                      loan_id='loan ID', policy_id='policy ID', ticket_id='ticket ID', class_id='class ID')
EN_CITIES = ['London','Paris','Berlin','Tokyo','Sydney','Boston','Seattle','Toronto','Singapore','Dublin','Madrid','Rome']
EN_SHOES = ['running shoes','canvas shoes','ankle boots']
EN_CLOTHES = ['dress','hoodie','jeans','coat']
EN_PRODUCTS = ['coffee maker','wireless keyboard','Bluetooth mouse','headphones','kettle','desk lamp'] + EN_SHOES + EN_CLOTHES
EN_ISSUES = {'damaged':['damaged','broken'], 'wrong_item':['wrong item','incorrect item'],
 'missing_item':['missing item','missing parts'], 'quality_issue':['quality problem','not working'],
 'not_as_described':['not as described','different from the description'],
 'size_mismatch':['wrong size','does not fit'], 'no_reason':['changed my mind','no longer needed']}
# The simulator's reason vocabulary remains the authoritative set.
import scenes as S
for key in S.ISSUE_TYPES:
    EN_ISSUES.setdefault(key, [key.replace('_',' ')])
EN_WANTS = {'return_refund':'return and refund', 'exchange':'exchange', 'refund_only':'refund without return'}


class EnglishMixin:
    def english_values(self, keys, scene):
        first, second = self.rng.sample(EN_CITIES,2)
        future = (self.today + timedelta(days=self.rng.randint(1,90))).isoformat()
        product = self.pick(EN_SHOES+EN_CLOTHES) if 'size' in keys else self.pick(EN_PRODUCTS)
        date = self.day()
        values = {
          'product':product, 'product2':self.pick([p for p in EN_PRODUCTS if p != product]), 'brand':self.pick(['Example Brand A','Example Brand B']),
          'order_id':self.oid(), 'tracking_no':self.oid('TRACK'), 'city':first, 'address':f'{self.rng.randint(1,999)} Example Street',
          'date':date, 'size':self.pick(S.SHOE_SIZES if product in EN_SHOES else ['S','M','L','XL','XXL']),
          'color':self.pick(['black','white','navy','red','beige']), 'phone':'***-***-'+f'{self.rng.randrange(10000):04d}',
          'name':self.pick(['Alex','Sam','Jordan','Taylor']), 'amount':self.amount(), 'payment':self.pick(['bank card','digital wallet','credit card']),
          'company':self.pick(['Example Trading Ltd','Example Technology Ltd']), 'tax_no':self.oid('TAX'), 'logistics':self.pick(['Example Courier A','Example Courier B']),
          'reason':self.pick(['damaged item','incorrect information','plans changed','duplicate request']),
          'coupon':self.pick(['10 percent off','new customer coupon','member discount']), 'level':self.pick(['standard','silver','gold','platinum']),
          'account_no':'account ending '+f'{self.rng.randrange(10000):04d}', 'card_no':'card ending '+f'{self.rng.randrange(10000):04d}',
          'bank':self.pick(['Example Bank A','Example Bank B','Example Bank C']), 'currency':self.pick(['USD','EUR','GBP']),
          'recipient':self.pick(['Alex','Sam','Jordan']), 'loan_id':self.oid('LN'), 'period':self.pick(['3 months','6 months','1 year','2 years']),
          'deposit_type':self.pick(['term deposit','fixed deposit']), 'fund_product':self.pick(['Example Fund A','Example Fund B']),
          'policy_id':self.oid('PL'), 'insurance_type':self.pick(['accident insurance','medical insurance','car insurance']),
          'departure':first,'destination':second,'travel_date':future,'ticket_id':self.oid('TK'), 'hotel_name':second+' Example Hotel',
          'checkin_date':future,'nights':str(self.rng.randint(1,14)), 'room_type':self.pick(['double room','twin room','family room']),
          'pickup':first+' Central Station','plan':self.pick(['basic data plan','family plan','student plan']), 'bill_month':date[:7],
          'service_id':self.oid('SV'), 'course_name':self.pick(['Python Basics','Business English','Introduction to Data Analysis','Photography Basics']),
          'student':self.pick(['Alex','Sam','Taylor']), 'class_id':self.oid('CL'), 'schedule_date':future,
          'login_method':self.pick(['SMS code','account and password','email code']),
        }
        result = {k:values[k] for k in keys}
        if product in EN_SHOES and 'size' in result: result['size'] = re.sub('码$', '',result['size'])
        self.values.extend(result.values())
        return result

    def values_for(self, scene):
        if self.language != 'en': return super().values_for(scene)
        return self.english_values(scene['slots'],scene)

    def intent(self, task):
        if self.language != 'en': return super().intent(task)
        scene = self.choose_scene(task)
        values = self.values_for(scene)
        keys = list(values)
        self.rng.shuffle(keys)
        if self.rng.random() < .25: keys = keys[:self.rng.randint(0,len(keys))]
        values = {k:values[k] for k in keys}
        action = self.pick(['Please {a}.','Could you {a}?','I would like to {a}.','Can you help me {a}?',
                            'I need to {a}.','How can I {a}?','Help me {a}, please.','I am contacting you to {a}.']).format(a=EN_ACTIONS[scene['id']])
        detail = self.pick([', ','; ','\n']).join(self.pick(['{k}: {v}','My {k} is {v}','{k} = {v}',
            'The {k} is {v}']).format(k=EN_SLOT_LABELS[k],v=values[k]) for k in keys)
        text = self.pick(['{a} {d}','{d}. {a}','{a}\nDetails: {d}','Here are my details: {d}. {a}']).format(a=action,d=detail) if detail else action
        if self.rng.random() < .2: text = self.pick(['Hello, ','Hi, ','Good morning, '])+text
        answer = {'domain':scene['domain']} if task == 'domain' else {'slots':values} if task == 'slots' else {'domain':scene['domain'],'intent':scene['intent'],'slots':values}
        return self.single(task,text,answer,scene['id'])

    def dst(self, task):
        if self.language != 'en': return super().dst(task)
        scene = self.choose_scene(task)
        domain = scene['domain']
        values = self.values_for(scene)
        state = {'intent':{'domain':domain,'slot':'intent','value':scene['intent'],'active':True}}
        lines = [f"User: For {domain}, intent is {scene['intent']}."]
        keys = list(values)
        self.rng.shuffle(keys)
        for slot in keys:
            value = values[slot]
            lines.append(f'User: For {domain}, {slot} is {value}.')
            state[slot] = {'domain':domain,'slot':slot,'value':value,'active':True}
            if self.rng.random() < .3:
                value = self.values_for(scene)[slot]
                lines.append(f'User: Correction: for {domain}, {slot} is {value}.')
                state[slot]['value'] = value
            if self.rng.random() < .1:
                lines.append(f'User: Withdraw {domain}.{slot}; leave it unset.')
                state[slot]['active'] = False
            if self.rng.random() < .5: lines.append(self.pick(['System: Understood.','System: Please continue.','System: I will use your latest details.']))
        entries = list(state.values())
        answer = entries if task == 'dst_user' else {e['domain']+'-'+e['slot']:e['value'] for e in entries if e['active']}
        return self.single(task,'\n'.join(lines),answer,scene['id'])

    def clarify(self):
        if self.language != 'en': return super().clarify()
        scene = self.choose_scene('clarify')
        values = self.values_for(scene)
        keys = list(values)
        self.rng.shuffle(keys)
        known = keys[:self.rng.randrange(len(keys))]
        missing = ', '.join(EN_SLOT_LABELS[k] for k in keys if k not in known)
        details = '; '.join(EN_SLOT_LABELS[k]+': '+values[k] for k in known)
        request = 'I would like to '+EN_ACTIONS[scene['id']]+'. '+details
        user = f"User request: {request}\nTopic: {EN_ACTIONS[scene['id']]}\nMissing information: {missing}."
        question = self.pick(['Could you provide {m}?','Please clarify {m}?','To proceed, could you tell me {m}?',
                              'May I confirm {m}?']).format(m=missing)
        return self.single('clarify',user,question,scene['id'])

    def ecom(self):
        if self.language != 'en': return super().ecom()
        if not self.agent_targets: raise ValueError('Select an e-commerce after-sales scenario for tool decisions')
        issue = self.pick(list(S.ISSUE_TYPES),'en:issue')
        want = self.pick(self.agent_wants or list(EN_WANTS),'en:want')
        flow = 'existing' if self.agent_progress_only else self.pick(['missing_order','normal','normal','existing','query_only','tool_failure'],'en:flow')
        order_id = self.oid()
        product = self.remember(self.pick(EN_PRODUCTS))
        status = self.pick(['pending','shipped','delivered','delivered'])
        days = self.pick([0,1,6,7,8,14,30]) if status == 'delivered' else None
        paid = self.pick(['paid','paid','refunded'])
        identity = self.pick(['verified','required'])
        evidence_required = issue in ('damaged','quality_issue','not_as_described')
        evidence = evidence_required and self.rng.random() < .55
        existing = {'request_id':self.oid('AS'),'request_type':want,'status':'submitted'} if flow == 'existing' else None
        messages = [{'role':'system','content':EN_SYS['ecom']}]
        def add(role,text): messages.append({'role':role,'content':text})
        def action(tool,params): add('assistant','Action: '+tool+'\nAction Input: '+json.dumps(params,ensure_ascii=False,sort_keys=True,separators=(',',':')))
        def result(tool,data,ok=True): add('user','Tool result: '+json.dumps({'tool':tool,'data':data,'ok':ok},ensure_ascii=False,sort_keys=True,separators=(',',':')))
        opening = f"My {product} is {self.pick(EN_ISSUES[issue])}. I would like a {EN_WANTS[want]}."
        if self.agent_progress_only: opening = 'Please check my existing after-sales request. Do not submit another request.'
        if flow == 'missing_order':
            add('user',opening)
            add('assistant','Please provide the order ID so I can check the order and policy.')
        else:
            if flow == 'query_only': opening += ' Check the policy only. Do not submit a request.'
            if evidence: opening += ' I have uploaded photos of the item problem.'
            add('user',f'Order ID: {order_id}. '+opening)
            action('query_order_status',{'order_id':order_id})
            if flow == 'tool_failure':
                result('query_order_status',{'error_code':'TIMEOUT'},False)
                add('assistant','The query failed. I cannot confirm the order status. Please check the order ID and try again later.')
            else:
                result('query_order_status',{'order_id':order_id,'fulfillment_status':status,'payment_status':paid,
                    'days_since_delivery':days,'identity_verification_status':identity,'after_sales_request':existing,'item_summary':product})
                if existing: add('assistant',f"An existing request {existing['request_id']} is submitted. No duplicate request is needed.")
                else:
                    if paid == 'refunded': allowed,code = [],'ALREADY_REFUNDED'
                    elif status != 'delivered': allowed,code = ['refund_only'],'NOT_DELIVERED'
                    elif days <= 7: allowed,code = list(EN_WANTS),'IN_WINDOW'
                    elif issue != 'no_reason' and days <= 30: allowed,code = ['return_refund','exchange'],'QUALITY_REVIEW'
                    else: allowed,code = [],'OUT_OF_WINDOW'
                    action('check_return_policy',{'order_id':order_id,'issue_type':issue})
                    result('check_return_policy',{'order_id':order_id,'issue_type':issue,'eligible':bool(allowed),
                        'allowed_request_types':allowed,'reason_code':code,'message':'Simulated policy result: '+code,
                        'evidence_required':evidence_required,'policy_version':'synthetic-v2'})
                    if flow == 'query_only': add('assistant','The policy check is complete. As requested, no request was submitted.')
                    elif want not in allowed: add('assistant','The requested action is unavailable under this simulated policy. Please confirm an available option or contact support.')
                    elif identity == 'required': add('assistant','Please complete identity verification before the request can be submitted.')
                    elif evidence_required and not evidence: add('assistant','Please upload photos of the item problem before proceeding.')
                    else:
                        action('create_after_sales_request',{'order_id':order_id,'request_type':want,'reason':issue})
                        rid = self.oid('AS')
                        result('create_after_sales_request',{'order_id':order_id,'request_type':want,'request_id':rid,'status':'submitted'})
                        add('assistant',f'The request was submitted successfully. Request ID: {rid}.')
        endpoints = [i for i,m in enumerate(messages) if i and m['role'] == 'assistant']
        if len(endpoints)>1 and self.rng.random()<.25: messages = messages[:self.pick(endpoints)+1]
        sample = self.single('ecom','unused','unused','ecom:agent:'+flow+'/'+issue+'/'+status)
        sample.obj = {'messages':messages}
        return sample


def validate_english_state(sample):
    facts = {}
    for line in sample.obj['messages'][1]['content'].splitlines():
        match = re.fullmatch(r'User: (?:For |Correction: for )(\w+), (\w+) is (.+)\.',line)
        if match:
            dom,slot,value = match.groups()
            facts[(dom,slot)] = {'domain':dom,'slot':slot,'value':value,'active':True}
        match = re.fullmatch(r'User: Withdraw (\w+)\.(\w+); leave it unset\.',line)
        if match:
            key = match.groups()
            if key not in facts: raise ValueError('Withdrawal has no prior value')
            facts[key]['active'] = False
    if not facts: raise ValueError('No grounded English dialogue state')
    answer = json.loads(sample.answer)
    if sample.task == 'dst_user':
        if not isinstance(answer,list) or len(answer) != len(facts): raise ValueError('Incomplete English dialogue state')
        expected = sorted(facts.values(),key=lambda e:(e['domain'],e['slot']))
        actual = sorted(answer,key=lambda e:(e['domain'],e['slot']))
        if actual != expected or any(type(e['active']) is not bool for e in answer): raise ValueError('Incorrect latest English dialogue state')
    else:
        expected = {d+'-'+s:e['value'] for (d,s),e in facts.items() if e['active']}
        if answer != expected: raise ValueError('Incorrect latest English belief state')
