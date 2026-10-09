"""Offline, seeded monitoring experiment. No network or external dependencies."""
import json
import math
import random
from pathlib import Path


def number(x, lo=0, hi=float('inf')):
    try:
        valid = type(x) in (int, float) and math.isfinite(x) and lo <= x <= hi
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('invalid or unrepresentable finite number')
    return x


def counts(k, n):
    if type(n) is not int or type(k) is not int or not 0 <= k <= n:
        raise ValueError('invalid counts')


def p_score(k, n, p):
    counts(k, n)
    number(p, 0, 1)
    if n == 0:
        return None
    if p in (0, 1):
        raise ValueError('degenerate baseline requires exact-binomial policy')
    try:
        variance = number(n*p*(1-p))
        if variance == 0:
            raise ValueError('unrepresentable positive variance')
        return number((k - n*p) / math.sqrt(variance), -float('inf'))
    except OverflowError as exc:
        raise ValueError('unrepresentable p-score arithmetic') from exc


def js(a, b):
    if not a or len(a) != len(b):
        raise ValueError('same nonempty category schema required')
    for x in a+b:
        number(x)
    if min(number(sum(a)), number(sum(b))) <= 0:
        raise ValueError('positive finite totals required')
    p = [x/sum(a) for x in a]
    q = [x/sum(b) for x in b]
    return sum(0.5*x*math.log2(2*x/(x+y)) if x else 0 for x,y in zip(p,q)) + sum(0.5*y*math.log2(2*y/(x+y)) if y else 0 for x,y in zip(p,q))


def cusum_step(state, z, allowance, threshold):
    for x in (state, allowance, threshold):
        number(x)
    if threshold == 0:
        raise ValueError('positive threshold required')
    if z is None:
        return state, False, state
    number(z, -float('inf'))
    total = number(state + z, -float('inf'))
    before_reset = max(0.0, number(total - allowance, -float('inf')))
    alarm = before_reset >= threshold
    return (0.0 if alarm else before_reset), alarm, before_reset


def generate(seed, injected=False, days=80):
    rng = random.Random(seed)
    rows = []
    for day in range(days):
        for i in range(200):
            # Always consume the same random draws for paired null/injected streams.
            u,v,w,t = [rng.random() for _ in range(4)]
            group = 'complex' if u < (0.35 if injected and day >= 40 else 0.2) else 'routine'
            probability = (0.22 if injected and day >= 40 else 0.10) if group == 'complex' else 0.02
            missing = injected and 55 <= day < 58 and i % 4 == 0
            rows.append(dict(id=f'{day}:{i}', day=day, group=group,
                refusal=None if missing else int(v < probability),
                outcome=None if day+3 > days-1 or missing else int(w >= probability),
                outcome_due=day+3, collected=not missing,
                latency_ms=None if missing else round(200+600*t+(150 if group=='complex' else 0), 3),
                cost_units=None if missing else (3 if group=='complex' else 1),
                agent_snapshot='lab-A', prompt='prompt-1', tool='tool-1',
                evaluator='eval-1', collector='collector-1'))
    return rows


def validate(rows):
    """Check fixture fields, not schedule completeness, versions or maturity."""
    seen=set(); previous=-1
    for r in rows:
        if type(r['id']) is not str or not r['id'] or r['id'] in seen:
            raise ValueError('duplicate or invalid identity')
        seen.add(r['id'])
        if type(r['day']) is not int or r['day'] < previous or r['day'] < 0:
            raise ValueError('out-of-order or invalid day')
        previous=r['day']
        if r['group'] not in ('complex','routine') or type(r['collected']) is not bool:
            raise ValueError('invalid category or collection flag')
        for key in ('refusal','outcome'):
            x=r[key]
            if x is not None and (type(x) is not int or x not in (0,1)):
                raise ValueError('invalid binary observation')
        if not r['collected'] and any(r[k] is not None for k in ('refusal','outcome','latency_ms','cost_units')):
            raise ValueError('missing collector cannot supply evidence')
        if r['collected'] and any(r[k] is None for k in ('refusal','latency_ms','cost_units')):
            raise ValueError('collected fixture requires refusal, latency and cost')
        for key in ('latency_ms','cost_units'):
            if r[key] is not None:
                number(r[key])


def aggregate(rows):
    validate(rows)
    out=[]
    for day in range(max((r['day'] for r in rows),default=-1)+1):
        rr=[r for r in rows if r['day']==day]
        for group in ('all','routine','complex'):
            selected=[r for r in rr if group=='all' or r['group']==group]
            obs=[r for r in selected if r['refusal'] is not None]
            outcomes=[r for r in selected if r['outcome'] is not None]
            out.append(dict(day=day,group=group,scheduled=len(selected),n=len(obs),
                k=sum(r['refusal'] for r in obs),outcomes=len(outcomes),
                successes=sum(r['outcome'] for r in outcomes),
                unknown_outcomes=len(selected)-len(outcomes),
                mean_latency_ms=number(sum(r['latency_ms'] for r in obs))/len(obs) if obs else None,
                cost_units=number(sum(r['cost_units'] for r in obs)) if obs else None))
    return out


def analyse(daily, z_limit=3.0, h=5.0, sliced=False):
    number(z_limit); number(h)
    if h == 0:
        raise ValueError('positive threshold required')
    seen=set(); previous=-1
    for r in daily:
        day=r['day']; group=r['group']
        if type(day) is not int or day < 0 or day < previous or group not in ('all','routine','complex'):
            raise ValueError('invalid or out-of-order daily record')
        if (day,group) in seen:
            raise ValueError('duplicate daily group record')
        seen.add((day,group)); previous=day
        counts(r['k'],r['n']); counts(r['n'],r['scheduled'])
    groups=('routine','complex') if sliced else ('all',)
    for g in groups:
        if sum(r['n'] for r in daily if r['group']==g and r['day']<20) == 0:
            raise ValueError('nonempty baseline required for '+g)
    baselines={g:sum(r['k'] for r in daily if r['group']==g and r['day']<20)/sum(r['n'] for r in daily if r['group']==g and r['day']<20) for g in groups}
    states={g:0.0 for g in groups}; result=[]
    for r in daily:
        g=r['group']
        if g not in groups or r['day']<20:
            continue
        # Any collection gap defers quality interpretation; scheduled denominator retained.
        z=p_score(r['k'],r['n'],baselines[g]) if r['n']==r['scheduled'] else None
        states[g],alarm,raw=cusum_step(states[g],z,0.5,h)
        result.append(dict(**r,z=z,cusum=raw,p_alarm=z is not None and z>=z_limit,c_alarm=alarm))
    return result


def metrics(result, field, null=False):
    alarms=sorted(set(r['day'] for r in result if r[field]))
    post=[d for d in alarms if d>=40]
    return dict(false_alarm_days=sum(d<40 or null for d in alarms),
                monitored_days=60 if null else 20,
                first_detection_day=None if null or not post else post[0],
                detection_delay_days=None if null or not post else post[0]-40)


def run():
    root=Path(__file__).resolve().parent
    out=root/'output'; out.mkdir(exist_ok=True)
    # Calibration is separate from assessment: finite grid, 8 known-null seeds.
    calibration=[]; chosen={}
    for sliced in (False,True):
        for z,h in ((2.5,4.0),(3.0,5.0),(3.5,7.0),(4.0,9.0),(4.5,12.0),(5.0,16.0)):
            p=c=0
            for seed in range(100,108):
                a=analyse(aggregate(generate(seed)),z,h,sliced)
                p+=metrics(a,'p_alarm',True)['false_alarm_days']
                c+=metrics(a,'c_alarm',True)['false_alarm_days']
            calibration.append(dict(sliced=sliced,z=z,h=h,p_alarm_days=p,c_alarm_days=c,days=480))
            if p/480 <= .01 and c/480 <= .01 and sliced not in chosen:
                chosen[sliced]=(z,h)
        if sliced not in chosen:
            raise RuntimeError('calibration grid exhausted')
    summary=[]; series={}
    for scenario in ('null','injected'):
        rows=generate(20261006,scenario=='injected')
        (out/f'{scenario}-raw.json').write_text(json.dumps(rows,indent=2))
        daily=aggregate(rows)
        (out/f'{scenario}-daily.json').write_text(json.dumps(daily,indent=2))
        for sliced in (False,True):
            for policy in ('default','calibrated'):
                z,h=chosen[sliced] if policy=='calibrated' else (3.0,5.0)
                a=analyse(daily,z,h,sliced)
                key=f'{scenario}-{sliced}-{policy}'; series[key]=a
                for detector,field in (('p-chart','p_alarm'),('CUSUM','c_alarm')):
                    summary.append(dict(scenario=scenario,sliced=sliced,policy=policy,detector=detector,z=z,h=h,**metrics(a,field,scenario=='null')))
    report=dict(seed=20261006,injection_day=40,baseline_days=[0,19],assessment_days=[20,79],calibration=calibration,summary=summary,series=series)
    (out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    run()
