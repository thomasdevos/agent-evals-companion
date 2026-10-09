"""Versioned offline task sessions; no network transport or measured model cost."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from native import Conversation, require, obj, text, canonical
from integration import Session, CategoryBudget, entries, read, storage
from chapter02 import task_lab as lab

SCHEMA = 'native-task-session-v1'
GRADER = 'chapter02-six-checks-v1'
FIELDS = {'ask': {'text': 'string'}, 'read': {'text': 'string'},
          'refund': {'order_id': 'string', 'amount_pence': 'integer'},
          'finish': {'status': 'string', 'reason': 'string', 'text': 'string'}}
TOOLS = [dict(type='function', name=k, description='Task action: '+k,
              parameters=dict(type='object', properties={f:dict(type=t) for f,t in v.items()},
                              required=list(v), additionalProperties=False)) for k,v in FIELDS.items()]

def action(name, args):
    require(name in FIELDS, 'unsupported_task_action')
    obj(args, FIELDS[name])
    for key, typ in FIELDS[name].items():
        if typ == 'string': text(args[key])
        else: require(type(args[key]) is int and 0 < args[key] <= 2**63-1, 'refund_integer')
    if name == 'finish': require(args['status'] in ('completed','refused'), 'terminal_status')
    return dict(kind=name, **deepcopy(args))

def binding(name):
    require(name in ('full','clarify','refuse'), 'unsupported_card')
    raw = (lab.HERE/'cards'/(name+'.json')).read_bytes()
    card = json.loads(raw); lab.validate_card(card)
    return card, dict(name=name, id=card['id'], bytes=raw.decode(), sha256=hashlib.sha256(raw).hexdigest())

class Environment:
    def __init__(self, card):
        self.steps = lab.trial_steps(deepcopy(card), 'native', snapshot_view=True)
        self.view = next(self.steps)
        self.outcome = None
    def __call__(self, call):
        require(self.outcome is None, 'task_terminal')
        try:
            self.view = self.steps.send(deepcopy(call))
        except StopIteration as done:
            self.outcome = done.value
        # The grader and expected outcome are never candidate-visible.
        visible = self.view if self.outcome is None else dict(after=self.outcome['after'], terminal=self.outcome['terminal'])
        return dict(is_error=False, output=canonical(visible))
    def finalise(self):
        if self.outcome is None:
            self(dict(kind='finish', status='completed', reason='unspecified', text='Native final text without task terminal.'))
        return deepcopy(self.outcome)
    def close(self): self.steps.close()

class TaskConversation(Conversation):
    def __init__(self, provider, prompt):
        super().__init__(provider, prompt, action, TOOLS)
    def accept(self, response):
        calls = super().accept(response)
        # Interactive and terminal actions cannot share a batch with other actions.
        try:
            require(not any(c['kind'] in ('ask','finish') for _,c in calls) or len(calls)==1,
                    'interactive_batch')
        except Exception:
            self._fault = True
            raise
        return calls
    def complete(self, results):
        asking = any(c['kind']=='ask' for _,c in self._pending)
        super().complete(results)
        if asking:
            view = json.loads(results[0]['output'])
            trace = view.get('trace', [])
            if trace and trace[-1]['kind']=='user_reply':
                reply = {k:v for k,v in trace[-1].items() if k!='kind'}
                self._history.append(dict(role='user', content=canonical(reply)))

class TaskSession(Session):
    def __init__(self, directory, provider, card_name, ceiling=100, store_factory=storage.CaptureStore):
        card, bound = binding(card_name)
        self.executor = Environment(card)
        prompt = canonical(dict(request=card['request'], policy=card['policy'], orders=card['start']['orders']))
        self._conversation = TaskConversation(provider, prompt)
        self.provider = provider
        self.budget = CategoryBudget(ceiling)
        self.stopped = False; self.turns = 0
        self.store = store_factory(directory, SCHEMA, ['trial:1'])
        self.contract = dict(schema=SCHEMA, provider=provider, card=bound, ceiling=ceiling, grader=GRADER)
        storage.atomic_json(self.store.directory/'contract.json', self.contract)
    def finish(self):
        require(not self.stopped and self._conversation._closed, 'unfinished_session')
        try:
            outcome = self.executor.finalise()
            storage.atomic_json(self.store.directory/'complete.json', dict(schema=SCHEMA,
                capture_complete=True, task_outcome=outcome, grader=GRADER,
                contract_sha256=storage.sha(self.contract), turns=self.turns,
                accounting=self.budget.report(), entries_sha256=storage.sha(entries(self.store.directory))))
            self.stopped = True
        except Exception:
            self.stopped = True; self.budget.blocked = True
            raise
        finally: self.executor.close()

def load(directory):
    d = Path(directory)
    bundle = dict(contract=read(d/'contract.json'), complete=read(d/'complete.json'), entries=entries(d))
    require(canonical(read(d/'manifest.json')) == canonical(dict(schema=1, identity=SCHEMA,
        schedule=['trial:1'], provenance='synthetic', policy='full-private', replayable=True)), 'manifest')
    validate(bundle)
    return bundle

def validate(bundle):
    obj(bundle, {'contract','complete','entries'})
    c, done, rows = bundle['contract'], bundle['complete'], bundle['entries']
    obj(c, {'schema','provider','card','ceiling','grader'})
    card, bound = binding(c['card']['name'])
    require(c['schema']==SCHEMA and c['grader']==GRADER and canonical(bound)==canonical(c['card']), 'card_binding')
    require(done['contract_sha256']==storage.sha(c) and done['entries_sha256']==storage.sha(rows), 'completion_binding')
    # Structural preflight of every retained response, before constructing a task environment.
    prompt = canonical(dict(request=card['request'], policy=card['policy'], orders=card['start']['orders']))
    probe = TaskConversation(c['provider'], prompt)
    responses = []
    for row in rows:
        if row['request']['kind']=='request':
            probe.request()
            response = row['result']['response']; calls = probe.accept(response)
            CategoryBudget(c['ceiling']).cost(c['provider'],response['usage'])
            if calls:
                # Preflight checks structural admission only; replay below checks actual history.
                Conversation.complete(probe,[dict(call_id=cid,is_error=False,output='{}') for cid,_ in calls])
            responses.append(response)
    with tempfile.TemporaryDirectory(prefix='task-replay-') as tmp:
        session = TaskSession(Path(tmp)/'capture', c['provider'], bound['name'], c['ceiling'])
        try:
            for response in responses: session.turn(lambda request, r=response: deepcopy(r))
            session.finish()
            require(canonical(entries(session.store.directory))==canonical(rows), 'native_history_or_effects')
            require(canonical(read(session.store.directory/'complete.json'))==canonical(done), 'task_outcome_or_accounting')
        finally: session.executor.close()
    return dict(capture_complete=True, task_status=done['task_outcome']['status'],
                checks=done['task_outcome']['checks'], after=done['task_outcome']['after'], accounting=done['accounting'])

def export(directory, destination):
    bundle = load(directory)
    out = Path(destination); out.mkdir(parents=True, exist_ok=False)
    storage.atomic_json(out/'bundle.json', bundle)
    storage.atomic_json(out/'seal.json', dict(schema=SCHEMA,sha256=storage.sha(bundle)))

def replay(directory):
    d=Path(directory); b=read(d/'bundle.json')
    require(read(d/'seal.json')==dict(schema=SCHEMA,sha256=storage.sha(b)), 'export_binding')
    return validate(b)
