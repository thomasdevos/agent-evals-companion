"""Durable synthetic support workflow, standard library, no network."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from first_eval import create_fixture, snapshot, grade, CASE
from chapter08.graders import snapshot_shape

OP = ('support-v1', 'refund-A100-full')
PAYLOAD = ('A100', 4200)
ACTORS = ('intake', 'payments')
KINDS = ('identity', 'policy', 'handoff', 'submit', 'timeout', 'reconcile', 'confirm', 'memory')

def initialise(path):
    create_fixture(path)
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''CREATE TABLE operations (scope TEXT, operation TEXT, order_id TEXT,
          amount INTEGER, actor TEXT, PRIMARY KEY(scope,operation));
          CREATE TABLE events (seq INTEGER PRIMARY KEY, actor TEXT, kind TEXT, scope TEXT, operation TEXT);
          CREATE TABLE memory_observations (seq INTEGER PRIMARY KEY, scope TEXT, operation TEXT, name TEXT, value TEXT);
          CREATE TABLE memory (name TEXT PRIMARY KEY, value TEXT);
          INSERT INTO memory VALUES ('refund_status','not_started');''')
        db.commit()

def validate_identity(op):
    if type(op) is not tuple or len(op) != 2 or any(type(v) is not str or not v for v in op):
        raise ValueError('operation identity')
    if op != OP:
        raise ValueError('foreign operation')

def event(db, actor, kind, op=OP):
    validate_identity(op)
    if type(actor) is not str or actor not in ACTORS or kind not in KINDS:
        raise ValueError('actor/kind')
    db.execute('INSERT INTO events(actor,kind,scope,operation) VALUES (?,?,?,?)', (actor,kind,*op))

def refund(path, op=OP, payload=PAYLOAD, actor='payments', unsafe=False):
    validate_identity(op)
    if type(payload) is not tuple or len(payload) != 2 or type(payload[0]) is not str or type(payload[1]) is not int or not 0 < payload[1] < 2**63:
        raise ValueError('payload shape')
    if actor != 'payments' or type(actor) is not str:
        raise PermissionError('payments role required')
    with closing(sqlite3.connect(path)) as db:
        db.execute('BEGIN IMMEDIATE')
        prior = db.execute('SELECT order_id,amount FROM operations WHERE scope=? AND operation=?', op).fetchone()
        if prior and prior != payload:
            raise ValueError('payload conflict')
        if payload != PAYLOAD:
            raise ValueError('task arguments')
        rows = list(db.execute('SELECT seq,actor,kind,scope,operation FROM events ORDER BY seq'))
        prefix = rows[:3]
        valid = (len(prefix)==3 and [r[0] for r in prefix]==[1,2,3]
            and [r[2] for r in prefix] in (['identity','policy','handoff'], ['policy','identity','handoff'])
            and all(r[1]=='intake' and tuple(r[3:])==op for r in prefix))
        # First effect requires precisely the valid intake prefix. Existing-result
        # lookup remains idempotent without requiring a timeout/recovery ceremony.
        if not valid or (not prior and len(rows)!=3):
            raise PermissionError('invalid operation-bound prerequisites')
        event(db,actor,'submit')
        if not prior or unsafe:
            db.execute('INSERT INTO refunds(order_id,amount_pence) VALUES (?,?)',payload)
        if not prior:
            db.execute('INSERT INTO operations VALUES (?,?,?,?,?)',(*op,*payload,actor))
        db.commit()
        return 'existing' if prior and not unsafe else 'committed'

def phase(path, stage, route='identity-first', unsafe=False):
    if stage == 'start':
        with closing(sqlite3.connect(path)) as db:
            for kind in (('identity','policy') if route=='identity-first' else ('policy','identity')):
                event(db,'intake',kind)
            event(db,'intake','handoff'); db.commit()
        refund(path)
        # Fault injection is AFTER the real local transaction commits.
        with closing(sqlite3.connect(path)) as db:
            event(db,'payments','timeout'); db.commit()
        return 75
    if stage != 'resume':
        raise ValueError('stage')
    with closing(sqlite3.connect(path)) as db:
        db.execute('BEGIN IMMEDIATE')
        observed = db.execute("SELECT value FROM memory WHERE name='refund_status'").fetchone()
        if observed is None:
            raise ValueError('missing memory')
        event(db,'payments','memory')
        seq = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO memory_observations VALUES (?,?,?,?,?)',
                   (seq,*OP,'refund_status',observed[0]))
        event(db,'payments','reconcile'); db.commit()
    result = refund(path,unsafe=unsafe)
    with closing(sqlite3.connect(path)) as db:
        event(db,'payments','confirm')
        db.execute("UPDATE memory SET value='confirmed' WHERE name='refund_status'")
        db.commit()
    return 0

def inspect(path):
    after = snapshot(path)
    snapshot_shape(after)
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        events = [list(r) for r in db.execute('SELECT seq,actor,kind,scope,operation FROM events ORDER BY seq')]
        operations = [list(r) for r in db.execute('SELECT scope,operation,order_id,amount,actor FROM operations ORDER BY scope,operation')]
        memory = [list(r) for r in db.execute('SELECT name,value FROM memory ORDER BY name')]
        observations = [list(r) for r in db.execute('SELECT seq,scope,operation,name,value FROM memory_observations ORDER BY seq')]
    return dict(after=after,events=events,operations=operations,memory=memory,memory_observations=observations)

def evaluate(before, evidence):
    snapshot_shape(before)
    if before != {'orders':[['A100',4200,'paid'],['B200',1900,'paid']], 'refunds':[]}:
        raise ValueError('starting state')
    if type(evidence) is not dict or set(evidence) != {'after','events','operations','memory','memory_observations'}:
        raise ValueError('evidence fields')
    snapshot_shape(evidence['after'])
    events=evidence['events']; operations=evidence['operations']; memory=evidence['memory']
    if type(events) is not list or type(operations) is not list or type(memory) is not list:
        raise ValueError('evidence lists')
    seen=set()
    for row in events:
        if type(row) is not list or len(row)!=5 or type(row[0]) is not int or row[0]<=0 or any(type(v) is not str for v in row[1:]):
            raise ValueError('event types')
        if row[0] in seen or row[1] not in ACTORS or row[2] not in KINDS or tuple(row[3:])!=OP:
            raise ValueError('event identity')
        seen.add(row[0])
    if [r[0] for r in events] != list(range(1,len(events)+1)):
        raise ValueError('missing or reordered events')
    for row in operations:
        if type(row) is not list or len(row)!=5 or any(type(row[i]) is not str for i in (0,1,2,4)) or type(row[3]) is not int:
            raise ValueError('operation types')
    keys=[tuple(r[:2]) for r in operations]
    if len(set(keys))!=len(keys) or any(k!=OP for k in keys):
        raise ValueError('operation identities')
    if memory not in ([['refund_status','not_started']],[['refund_status','confirmed']]):
        raise ValueError('memory shape')
    kinds=[r[2] for r in events]
    # Every occurrence is accounted for; only the two preliminary reads commute.
    partial=(kinds[:2] in (['identity','policy'],['policy','identity']) and
             kinds[2:]==['handoff','submit','timeout','memory','reconcile','submit','confirm'])
    roles=all(r[1]==('intake' if r[2] in ('identity','policy','handoff') else 'payments') for r in events)
    durable=operations==[[*OP,*PAYLOAD,'payments']]
    checks=grade(before,evidence['after'],CASE)
    financial='PASS' if all(checks.values()) else 'FAIL'
    # A completed local report requires the authored bounded recovery protocol.
    counts={k:kinds.count(k) for k in KINDS}
    protocol=counts==dict(identity=1,policy=1,handoff=1,submit=2,timeout=1,reconcile=1,confirm=1,memory=1)
    observations=evidence['memory_observations']
    if type(observations) is not list or any(type(r) is not list or len(r)!=5 or type(r[0]) is not int or any(type(v) is not str for v in r[1:]) for r in observations):
        raise ValueError('memory observation shape')
    memory_consistent=(observations==[[6,*OP,'refund_status','not_started']] and
                       memory==[['refund_status','confirmed']] and partial)
    consistent=durable and evidence['after']['refunds']==[['A100',4200]] and memory_consistent
    return dict(financial=financial,checks=checks,partial_order=partial,roles=roles,
        protocol_complete=protocol,trace_state_consistent=consistent,
        outcome='PASS' if financial=='PASS' and partial and roles and protocol and consistent else 'FAIL',
        unnecessary_calls=max(0,len(events)-9), authentication='not established')

def scenario(unsafe=False,route='identity-first',directory=None):
    with tempfile.TemporaryDirectory(prefix='state14-') as td:
        path=Path(directory or td)/'support.sqlite'
        initialise(path); before=snapshot(path)
        base=[sys.executable]+(['-O'] if sys.flags.optimize else [])+['-m','chapter15.state_lab']
        first=subprocess.run(base+['phase',str(path),'start',route],capture_output=True,text=True)
        if first.returncode!=75: raise RuntimeError(first.stderr or 'interruption missing')
        interrupted=inspect(path)
        second=subprocess.run(base+['phase',str(path),'resume',route]+(['--unsafe'] if unsafe else []),capture_output=True,text=True)
        if second.returncode: raise RuntimeError(second.stderr)
        evidence=inspect(path)
        return dict(schema='chapter14-local-v2',scripted=True,fault='authored post-commit lost reply',
            start_exit=first.returncode,resume_exit=second.returncode,before=before,
            interrupted=interrupted,evidence=evidence,grade=evaluate(before,evidence))

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('mode',choices=['run','failure','repair','exercise','phase'])
    parser.add_argument('args',nargs='*'); parser.add_argument('--unsafe',action='store_true'); a=parser.parse_args()
    if a.mode=='phase': return phase(Path(a.args[0]),a.args[1],a.args[2],a.unsafe)
    if a.mode=='exercise':
        report={route:scenario(route=route) for route in ('identity-first','policy-first')}
    else: report=scenario(unsafe=a.mode=='failure')
    out=Path('chapter15/output'); out.mkdir(parents=True,exist_ok=True)
    (out/(a.mode+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 1 if a.mode=='failure' else 0
if __name__=='__main__': raise SystemExit(main())
