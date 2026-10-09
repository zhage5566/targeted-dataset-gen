"""Readable Chinese labels with stable canonical identifiers inside the generator."""
import copy
import json
import catalogue as C
from language_support import EN_ACTIONS

DOMAINS_ZH = C.DOMAINS
DOMAINS_EN = {v: k for k, v in DOMAINS_ZH.items()}
DOMAINS_EN.update({k.replace('_',' '):k for k in C.DOMAINS})
SLOTS_EN = {v: k for k, v in C.SLOT_LABELS.items()}
INTENTS_ZH = {(s['domain'], s['intent']): s['action'] for s in C.SCENARIOS}
INTENTS_EN = {(s['domain'], s['intent']): EN_ACTIONS[s['id']] for s in C.SCENARIOS}


def canonical_answer(answer, task=None):
    if not isinstance(answer, dict): return answer
    value = copy.deepcopy(answer)
    if 'domain' in value: value['domain'] = DOMAINS_EN.get(value['domain'], value['domain'])
    if 'intent' in value:
        matches = [s for s in C.SCENARIOS if s['domain'] == value.get('domain') and value['intent'] in (s['action'],EN_ACTIONS[s['id']])]
        if len(matches) == 1: value['intent'] = matches[0]['intent']
    if isinstance(value.get('slots'), dict):
        value['slots'] = {SLOTS_EN.get(k,k):v for k,v in value['slots'].items()}
    elif task == 'slots': value = {SLOTS_EN.get(k,k):v for k,v in value.items()}
    return value


def normalize_state(answer, task, language):
    if task not in ('dst_user','dst_belief'): return answer
    value = copy.deepcopy(answer)
    entries = value if task == 'dst_user' else [dict(domain=k.split('-',1)[0],slot=k.split('-',1)[1],value=v) for k,v in value.items()]
    normalized = []
    for e in entries:
        dom = DOMAINS_EN.get(e['domain'],e['domain'])
        slot = SLOTS_EN.get(e['slot'],e['slot'])
        if slot == '诉求': slot = 'intent'
        if slot == 'intent':
            code = canonical_answer({'domain':dom,'intent':e['value']})['intent']
            e['value'] = INTENTS_ZH.get((dom,code),code) if language == 'zh' else code
        e['domain'] = DOMAINS_ZH.get(dom,dom) if language == 'zh' else dom
        e['slot'] = ('诉求' if slot == 'intent' else C.SLOT_LABELS.get(slot,slot)) if language == 'zh' else slot
        normalized.append(e)
    return normalized if task == 'dst_user' else {e['domain']+'-'+e['slot']:e['value'] for e in normalized}


def localize_sample(sample, policy):
    language = getattr(sample, 'language', 'zh')
    if policy == 'follow': policy = language
    if policy == 'canonical': return sample
    try: answer = json.loads(sample.answer)
    except ValueError: return sample
    result = copy.deepcopy(sample)
    if sample.task in ('intent', 'domain', 'slots'):
        answer = canonical_answer(answer, sample.task)
        domain = answer.get('domain')
        if policy == 'zh':
            if 'intent' in answer: answer['intent'] = INTENTS_ZH.get((domain,answer['intent']), answer['intent'])
            if 'domain' in answer: answer['domain'] = DOMAINS_ZH.get(domain,domain)
        elif policy == 'en':
            if 'intent' in answer: answer['intent'] = INTENTS_EN.get((domain,answer['intent']),answer['intent'])
            if 'domain' in answer: answer['domain'] = domain.replace('_',' ')
    elif sample.task == 'dst_user':
        for entry in answer:
            dom = DOMAINS_EN.get(entry['domain'],entry['domain'])
            slot = SLOTS_EN.get(entry['slot'],entry['slot'])
            if entry['slot'] == '诉求': slot = 'intent'
            if policy == 'zh':
                entry['domain'] = DOMAINS_ZH.get(dom,dom)
                entry['slot'] = '诉求' if slot == 'intent' else C.SLOT_LABELS.get(slot,slot)
                if slot == 'intent': entry['value'] = INTENTS_ZH.get((dom,entry['value']),entry['value'])
            else:
                entry['domain'], entry['slot'] = dom.replace('_',' '), slot
                if slot == 'intent':
                    match = next((s for s in C.SCENARIOS if s['domain'] == dom and s['action'] == entry['value']),None)
                    if match: entry['value'] = match['intent']
                    entry['value'] = INTENTS_EN.get((dom,entry['value']),entry['value'])
    elif sample.task == 'dst_belief':
        mapped = {}
        for key,value in answer.items():
            dom,slot = key.split('-',1)
            dom,slot = DOMAINS_EN.get(dom,dom), SLOTS_EN.get(slot,slot)
            if slot == '诉求': slot = 'intent'
            if policy == 'zh':
                if slot == 'intent': value = INTENTS_ZH.get((dom,value),value)
            else:
                if slot == 'intent':
                    match = next((s for s in C.SCENARIOS if s['domain'] == dom and s['action'] == value),None)
                    if match: value = match['intent']
                    value = INTENTS_EN.get((dom,value),value)
            mapped[key] = value
        answer = mapped
    result.obj['messages'][-1]['content'] = json.dumps(answer, ensure_ascii=False, sort_keys=True, separators=(',',':'))
    return result
