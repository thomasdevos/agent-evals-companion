"""Chapter 5: cumulative harness. Offline fixtures are not provider measurements."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request
from chapter02.task_lab import run_trial, scripted_agent
from chapter03.dataset_lab import load_rows

class Fault(Exception):
    def __init__(self, status, reason):
        self.status, self.reason = status, reason
        super().__init__(reason)

class TransportError(Exception):
    pass

TOOLS = []
for name, props in {
    'ask': {'text': {'type':'string'}},
    'read': {'text': {'type':'string'}},
    'refund': {'order_id': {'type':'string'}, 'amount_pence': {'type':'integer'}},
}.items():
    TOOLS.append(dict(type='function', name=name, description='Synthetic support action: '+name,
        strict=True, parameters=dict(type='object', properties=props,
            required=list(props), additionalProperties=False)))

class HTTPTransport:
    """No SDK, redirects disabled, no automatic retries and no response-body logging."""
    def __call__(self, payload, timeout):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        key = os.environ.get('OPENAI_API_KEY')
        if not key:
            raise TransportError('missing_credential')
        req = urllib.request.Request('https://api.openai.com/v1/responses',
            data=json.dumps(payload).encode(), headers={
                'Authorization':'Bearer '+key, 'Content-Type':'application/json'})
        try:
            with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as response:
                return json.loads(response.read())
        except Exception:
            # Never include headers, credentials or arbitrary provider error bodies.
            raise TransportError('http_or_decode_error') from None

class ProviderAgent:
    """Responses wire adapter; invoked by Chapter 2's bounded action executor."""
    def __init__(self, transport, model='fixture-only', retry=False, requests=8, seconds=30):
        self.transport, self.model, self.retry = transport, model, retry
        self.cap, self.deadline = requests, time.monotonic()+seconds
        self.history, self.queue, self.pending = [], [], None
        self.requests, self.attempts, self.tool_calls = 0, 0, 0
        self.usage, self.error = [], None
        self.call_observation_complete = True
        self.cancelled = False
        self.call_ids = set()

    def fail(self, status, reason, provider_code=None):
        self.error = dict(status=status, reason=reason)
        if provider_code is not None:
            self.error['provider_code'] = provider_code
        raise Fault(status, reason)

    def check(self):
        if self.cancelled:
            self.fail('INFRA_ERROR', 'cancelled_cooperatively')
        if time.monotonic() >= self.deadline:
            self.fail('INFRA_ERROR', 'local_deadline')

    def __call__(self, view):
        self.check()
        if not self.history:
            self.history = [dict(role='system', content=(
                'Handle this synthetic support task. Use tools for actions. Ask once if identity is missing. '
                'Final response MUST be a JSON object with status completed or refused, reason full_refund '
                'or not_owned, and nonempty text. Do not emit final text alongside tool calls.')),
                dict(role='user', content=json.dumps({k:view[k] for k in ('request','policy','orders')}))]
        if self.pending:
            # The executor completed this action before calling us again. Include observed trace,
            # not a guessed refund result. Storage errors terminate without this callback.
            self.history.append(dict(type='function_call_output', call_id=self.pending,
                                     output=json.dumps(view['trace'])))
            self.pending = None
        if not self.queue:
            for attempt in range(2 if self.retry else 1):
                self.check()
                if self.requests >= self.cap:
                    self.fail('AGENT_ERROR', 'request_budget')
                self.requests += 1
                self.attempts += 1
                payload=dict(model=self.model, input=deepcopy(self.history), tools=TOOLS,
                             max_output_tokens=512, store=False)
                try:
                    response = self.transport(payload, max(0.001, self.deadline-time.monotonic()))
                    self.usage.append(response.get('usage') if isinstance(response, dict) else None)
                    # Observe before deadline/status/strict batch validation. This is a
                    # known lower bound when the envelope has unreadable companions.
                    output = response.get('output') if isinstance(response, dict) else None
                    if isinstance(output, list):
                        self.tool_calls += sum(isinstance(x, dict) and x.get('type') == 'function_call' for x in output)
                        if any(not isinstance(x, dict) or x.get('type') not in ('function_call','message','reasoning') for x in output):
                            self.call_observation_complete = False
                    else:
                        self.call_observation_complete = False
                    break
                except TransportError:
                    self.usage.append(None)
                    self.call_observation_complete = False
                    if attempt == (1 if self.retry else 0):
                        self.fail('INFRA_ERROR', 'provider_transport')
            self.check()
            try:
                status = response['status']
                if not isinstance(status, str):
                    raise ValueError()
                error = response.get('error')
                code = error.get('code') if isinstance(error, dict) else None
                if status == 'failed' and code in ('server_error','rate_limit_exceeded'):
                    self.fail('INFRA_ERROR', 'provider_service', code)
                if status == 'incomplete':
                    self.fail('AGENT_ERROR', 'provider_noncompleted')
                if status != 'completed':
                    # Cancellation and unknown failure causes cannot establish agent fault.
                    self.fail('INFRA_ERROR', 'provider_cancelled' if status == 'cancelled' else 'provider_status_unknown')
                output=response['output']
                if not isinstance(output, list) or not output:
                    raise ValueError()
                calls=[x for x in output if x['type']=='function_call']
                messages=[x for x in output if x['type']=='message']
                if any(x['type'] not in ('function_call','message','reasoning') for x in output):
                    raise ValueError()

                if calls and messages:
                    raise ValueError()
                actions=[]
                for call in calls:
                    cid=call['call_id']; name=call['name']
                    if not isinstance(cid,str) or not cid or cid in self.call_ids:
                        raise ValueError()
                    self.call_ids.add(cid)
                    spec=next((t for t in TOOLS if t['name']==name),None)
                    args=json.loads(call['arguments'])
                    if spec is None or type(args) is not dict or set(args)!=set(spec['parameters']['properties']):
                        raise ValueError()
                    for key, rule in spec['parameters']['properties'].items():
                        if type(args[key]) is not (int if rule['type']=='integer' else str):
                            raise ValueError()
                    actions.append((cid,dict(kind=name,**args)))
                self.history.extend(deepcopy(output))
                if actions:
                    self.queue=actions
                else:
                    text=''.join(c['text'] for m in messages for c in m['content'] if c['type']=='output_text')
                    final=json.loads(text)
                    if type(final) is not dict or set(final)!= {'status','reason','text'}:
                        raise ValueError()
                    return dict(kind='finish',**final)
            except Fault:
                raise
            except Exception:
                self.fail('AGENT_ERROR', 'malformed_provider_response')
        self.pending, action=self.queue.pop(0)
        return action

class FixtureTransport:
    """Synthetic wire messages derived from the published script, never recordings."""
    def __init__(self, transient=False):
        self.transient=transient
        self.calls=0
    def __call__(self, payload, timeout):
        self.calls+=1
        if self.transient and self.calls==1:
            raise TransportError('injected')
        view=json.loads(payload['input'][1]['content'])
        outputs=[i for i in payload['input'] if i.get('type')=='function_call_output']
        view['trace']=json.loads(outputs[-1]['output']) if outputs else []
        replies=[e for e in view['trace'] if e['kind']=='user_reply']
        if replies: view['request']['order_id']=replies[-1]['order_id']
        action=scripted_agent('corrected')(view)
        if action['kind']=='finish':
            output=[dict(type='message', role='assistant', content=[dict(type='output_text',
                         text=json.dumps({k:v for k,v in action.items() if k!='kind'}))])]
        else:
            output=[dict(type='function_call', call_id='call-'+str(self.calls), name=action.pop('kind'),
                         arguments=json.dumps(action))]
        return dict(status='completed', output=output, usage=None)

def execute(row, mode='fixture', retry=False, fault=None, model='fixture-only'):
    started=time.monotonic()
    adapter=None
    calls=0
    if mode in ('fixture','provider'):
        adapter=ProviderAgent(HTTPTransport() if mode=='provider' else FixtureTransport(fault=='transient'),
                              model=model, retry=retry)
        choose=adapter
    else:
        choose=scripted_agent('corrected')
    def invoke(view):
        nonlocal calls
        calls+=1
        if fault=='crash':
            raise RuntimeError('injected_agent_crash')
        if fault=='unavailable':
            if adapter: adapter.error=dict(status='INFRA_ERROR',reason='tool_unavailable')
            raise Fault('INFRA_ERROR','tool_unavailable')
        return choose(view)
    result=run_trial(row['card'], mode, invoke)
    result['adapter_error'] = deepcopy(adapter.error) if adapter else None
    if adapter and adapter.error:
        # A subsequent snapshot/storage failure takes precedence; retain both.
        if result['status'] not in ('INFRA_ERROR','GRADER_ERROR'):
            result['status']=adapter.error['status']; result['error']=adapter.error['reason']
    if fault=='unavailable' and result['status']=='AGENT_ERROR': result['status']='INFRA_ERROR'
    if result.get('stop')=='action_budget':
        result['status']='AGENT_ERROR'; result['error']='action_budget'
    result.update(passed=int(result['status']=='PASS'),failed=int(result['status']=='FAIL'),
                  errors=int(result['status'] not in ('PASS','FAIL')))
    result['scoring_eligible'] = result['status'] in ('PASS','FAIL')
    result['checks_role'] = ('unavailable' if result['checks'] is None else
                             'scoring' if result['scoring_eligible'] else 'diagnostic')
    result['ledger']=dict(agent_invocations=calls, request_attempts=adapter.requests if adapter else 0,
        provider_tool_calls=adapter.tool_calls if adapter else 0,
        provider_call_observation='complete' if not adapter or adapter.call_observation_complete else 'partial_or_unknown',
        executor_action_attempts=sum(e['kind'] in ('ask','read','refund','change_order') for e in result['trace']),
        usage=adapter.usage if adapter else [], model_cost=None if adapter else 0,
        cost_basis='unknown; no pricing supplied' if adapter else 'no model requests',
        elapsed_local_seconds=time.monotonic()-started)
    result.update(trial_id=row['case_id']+':1', family=row['family'],
                  provenance=deepcopy(row['provenance']), variant_group=row['variant_group'])
    return result

def run(dataset, mode='fixture', retry=False, fault=None, model='fixture-only', limit=None):
    rows=load_rows(dataset)
    if limit: rows=rows[:limit]
    trials=[execute(row,mode,retry,fault if i==0 or fault=='transient' else None,model)
            for i,row in enumerate(rows)]
    counts=Counter(t['status'] for t in trials)
    return dict(schema='chapter05-run-v2', dataset_sha256=hashlib.sha256(Path(dataset).read_bytes()).hexdigest(),
        scope='synthetic fixture; no measured provider behaviour' if mode!='provider' else 'live provider invocation',
        mode=mode, baseline='bounded-retry' if retry else 'direct',
        policy=dict(max_requests_per_trial=8,max_actions_per_trial=6,max_output_tokens_per_request=512,
                    cooperative_seconds=30,transport_attempts_per_request=2 if retry else 1),
        scheduled_trials=len(rows),reported_trials=len(trials),counts=dict(counts),trials=trials)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--dataset',default='chapter03/repaired.jsonl')
    p.add_argument('--mode',choices=['script','fixture','provider'],default='fixture')
    p.add_argument('--retry',action='store_true')
    p.add_argument('--fault',choices=['crash','unavailable','transient'])
    p.add_argument('--authorise-live',action='store_true')
    p.add_argument('--model',default='fixture-only')
    p.add_argument('--output',default='chapter05-report.json')
    a=p.parse_args()
    if a.mode=='provider' and (not a.authorise_live or a.model=='fixture-only'):
        print('Live mode requires explicit authorisation and model. No request sent.'); return 2
    try:
        report=run(a.dataset,a.mode,a.retry,a.fault,a.model,1 if a.mode=='provider' else None)
    except Exception as exc:
        report=dict(status='INVALID_DATASET',error=type(exc).__name__,scheduled_trials=None,counts={})
    Path(a.output).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='trials'},sort_keys=True))
    return 0 if report.get('counts',{}).get('PASS',0)==report.get('scheduled_trials') else 2

if __name__=='__main__':
    raise SystemExit(main())
