"""Live run: the book's harness against real models, with a frozen plan, a spending
ceiling reserved before every request, durable capture and a report in the book's shape.

Run from reader-package/:
    python3 live/live_run.py --plan live/plan-local.json --out live/results/dry --dry-run
    python3 live/live_run.py --plan my-plan.json --out live/results/run-1 --authorise-live

This command is deliberately separate from run.py, which refuses live arguments.
"""
import argparse
from collections import Counter
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
COMPANION = HERE.parent / 'core' / 'companion'
sys.path.insert(0, str(COMPANION))
sys.path.insert(0, str(HERE))

from chapter02.task_lab import run_trial          # noqa: E402
from chapter03.dataset_lab import load_rows       # noqa: E402
from chapter05.harness import ProviderAgent, Fault  # noqa: E402
import providers                                   # noqa: E402

DATASET = COMPANION / 'chapter03' / 'repaired.jsonl'
SCHEMA = 'live-run-v1'
MTOK = Decimal(1_000_000)


class BudgetStop(Exception):
    pass


class Budget:
    """Reserve a byte-based estimate before dispatch; unknown usage keeps the hold.

    Serialized bytes are not a guaranteed bound on provider billing or hidden overhead.
    Prices are supplied USD tariffs; use provider-side limits as well.
    """
    def __init__(self, ceiling, currency):
        self.ceiling, self.currency = Decimal(str(ceiling)), currency
        self.settled, self.held, self.unknown_requests = Decimal(0), Decimal(0), 0
        self.bound_exceeded = False

    def reserve(self, payload, max_out, price):
        if self.bound_exceeded:
            raise BudgetStop()
        bound = Decimal(len(json.dumps(payload).encode())) * Decimal(str(price['input'])) / MTOK
        bound += Decimal(max_out) * Decimal(str(price['output'])) / MTOK
        bound = bound.quantize(Decimal('0.000001'), rounding=ROUND_CEILING)
        if self.settled + self.held + bound > self.ceiling:
            raise BudgetStop()
        self.held += bound
        return bound

    def settle(self, reservation, usage, price):
        tokens = _tokens(usage)
        if tokens is None:
            self.unknown_requests += 1
            return None  # reservation stays held
        cost = (Decimal(tokens[0]) * Decimal(str(price['input'])) +
                Decimal(tokens[1]) * Decimal(str(price['output']))) / MTOK
        self.held -= reservation
        self.settled += cost
        if cost > reservation:
            self.bound_exceeded = True
        return cost

    def summary(self):
        return dict(currency=self.currency, ceiling=str(self.ceiling), settled=str(self.settled),
                    held_for_unknown_usage=str(self.held), unknown_usage_requests=self.unknown_requests,
                    total_known=self.unknown_requests == 0 and self.held == 0, reservation_exceeded=self.bound_exceeded,
                    reservation_basis='serialized_request_bytes_estimate_not_provider_billing_guarantee')


def _tokens(usage):
    """Return (input, output) when usage is complete and uncached, else None."""
    if not isinstance(usage, dict):
        return None
    i, o = usage.get('input_tokens'), usage.get('output_tokens')
    if type(i) is not int or type(o) is not int or i < 0 or o < 0:
        return None
    for key in ('cache_creation_input_tokens', 'cache_read_input_tokens'):
        value = usage.get(key, 0)
        if type(value) is not int or value != 0:
            return None
    details = usage.get('input_tokens_details', {})
    if type(details) is not dict:
        return None
    cached = details.get('cached_tokens', 0)
    if type(cached) is not int or cached != 0:
        return None  # cache categories are priced differently; do not guess
    return i, o


class Capture:
    """Append-only JSONL, flushed and fsynced: intent before each request, outcome after."""
    def __init__(self, path):
        self.f = os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8')
    def close(self):
        self.f.close()

    def write(self, record):
        self.f.write(json.dumps(record, sort_keys=True) + '\n')
        self.f.flush()
        os.fsync(self.f.fileno())


class MeteredTransport:
    """Wraps a transport with budget, capture and per-request latency."""
    def __init__(self, inner, budget, capture, price, max_out, context):
        self.inner, self.budget, self.capture = inner, budget, capture
        self.price, self.max_out, self.context = price, max_out, context
        self.latencies, self.served, self.stopped = [], [], False
        self.seq, self.stop_reason, self.dispatched = 0, None, 0

    def stop(self, reason):
        self.stopped, self.stop_reason = True, reason
        raise Fault('INFRA_ERROR', reason)

    def write(self, record):
        try:
            self.capture.write(record)
        except Exception:
            self.stop('capture_failure')

    def __call__(self, payload, timeout):
        if self.stopped:
            self.stop(self.stop_reason)
        payload = dict(payload)
        cap_key = 'max_tokens' if self.context.get('provider') == 'anthropic' else 'max_output_tokens'
        payload[cap_key] = self.max_out
        self.seq += 1
        try:
            hold = self.budget.reserve(payload, self.max_out, self.price)
        except BudgetStop:
            self.write(dict(event='budget_stop', seq=self.seq, **self.context))
            self.stop('budget_stop')
        self.write(dict(event='intent', seq=self.seq, reserved=str(hold), request=payload, **self.context))
        started = time.monotonic()
        try:
            self.dispatched += 1
            response = self.inner(payload, timeout)
        except Exception as exc:
            self.latencies.append(time.monotonic() - started)
            self.budget.settle(hold, None, self.price)
            self.write(dict(event='transport_error', seq=self.seq, error=type(exc).__name__,
                                    reservation_held=str(hold), **self.context))
            self.stop('transport_uncertain')
        elapsed = time.monotonic() - started
        self.latencies.append(elapsed)
        usage = response.get('usage') if isinstance(response, dict) else None
        cost = self.budget.settle(hold, usage, self.price)
        served = response.get('model') if isinstance(response, dict) else None
        self.served.append(served if type(served) is str else None)
        self.write(dict(event='response', seq=self.seq, elapsed_seconds=round(elapsed, 4),
                                served_model=served, usage=usage,
                                cost=None if cost is None else str(cost), response=response, **self.context))
        if cost is None:
            self.stop('unknown_usage')
        if self.budget.bound_exceeded:
            self.stop('reservation_exceeded')
        return response


def select_rows(task_ids):
    rows = {r['case_id']: r for r in load_rows(str(DATASET))}
    missing = [t for t in task_ids if t not in rows]
    if missing:
        raise SystemExit(f'Unknown task ids in plan: {missing}')
    return [rows[t] for t in task_ids]


def validate_plan(plan):
    required = {'name', 'owner', 'stop_authority', 'tasks', 'trials_per_task', 'models',
                'currency', 'ceiling', 'max_output_tokens', 'max_requests_per_trial',
                'seconds_per_trial', 'predictions'}
    if type(plan) is not dict or not required <= set(plan) or set(plan) - required - {'retry'}:
        raise SystemExit('Plan fields do not match the template; never put credentials in a plan.')
    def text(value):
        return type(value) is str and bool(value.strip()) and not any(
            marker in value.upper() for marker in ('REPLACE', 'TODO', 'TBD'))
    def positive(value):
        return type(value) in (int, float) and Decimal(str(value)).is_finite() and value > 0
    for key in ('name', 'owner', 'stop_authority'):
        if not text(plan[key]):
            raise SystemExit(f'{key} must be nonempty text, not a placeholder.')
    if plan['currency'] != 'USD':
        raise SystemExit('This kit supports USD tariffs only; currency conversion is not implemented.')
    for key in ('ceiling', 'seconds_per_trial'):
        if not positive(plan[key]):
            raise SystemExit(f'{key} must be finite and positive, not a boolean.')
    for key in ('trials_per_task', 'max_output_tokens', 'max_requests_per_trial'):
        if type(plan[key]) is not int or plan[key] < 1:
            raise SystemExit(f'{key} must be a positive integer.')
    if type(plan.get('retry', False)) is not bool:
        raise SystemExit('retry must be a JSON boolean.')
    tasks = plan['tasks']
    if type(tasks) is not list or not tasks or not all(text(t) for t in tasks) or len(set(tasks)) != len(tasks):
        raise SystemExit('tasks must be a nonempty list of unique task IDs.')
    p = plan['predictions']
    if type(p) is not dict or set(p) != {'expected_pass_rate', 'expected_most_common_failure'} or not all(text(v) for v in p.values()):
        raise SystemExit('Write both predictions as nonempty text without placeholders before running.')
    if type(plan['models']) is not list or not plan['models']:
        raise SystemExit('models must be a nonempty list.')
    identities = set()
    for m in plan['models']:
        if type(m) is not dict or set(m) != {'provider', 'model', 'price_per_mtok', 'price_source'}:
            raise SystemExit('Each model must match the template; credentials belong only in the environment.')
        if m['provider'] not in ('anthropic', 'openai') or not text(m['model']) or not text(m['price_source']):
            raise SystemExit('Provide supported provider, exact model ID and dated tariff source; no placeholders.')
        identity = (m['provider'], m['model'])
        if identity in identities:
            raise SystemExit('Duplicate provider/model entry.')
        identities.add(identity)
        price = m['price_per_mtok']
        if type(price) is not dict or set(price) != {'input', 'output'} or not all(positive(v) for v in price.values()):
            raise SystemExit('Prices must be finite positive numbers from a dated USD tariff, not booleans.')


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON member')
        result[key] = value
    return result


def make_agent(model_cfg, plan, transport):
    if model_cfg['provider'] == 'anthropic':
        return providers.MessagesAgent(transport, model_cfg['model'], retry=plan.get('retry', False),
                                       requests=plan['max_requests_per_trial'],
                                       seconds=plan['seconds_per_trial'],
                                       max_tokens=plan['max_output_tokens'])
    agent = ProviderAgent(transport, model=model_cfg['model'], retry=plan.get('retry', False),
                          requests=plan['max_requests_per_trial'], seconds=plan['seconds_per_trial'])
    return agent


def run_one(row, trial_no, model_cfg, plan, budget, capture, dry_fault):
    context = dict(case_id=row['case_id'], trial=trial_no, provider=model_cfg['provider'],
                   requested_model=model_cfg['model'])
    if dry_fault is not None:
        inner = providers.FakeAnthropic(dry_fault or None) if model_cfg['provider'] == 'anthropic' else providers.FakeOpenAI()
    else:
        inner = providers.AnthropicTransport() if model_cfg['provider'] == 'anthropic' else providers.OpenAITransport()
    meter = MeteredTransport(inner, budget, capture, model_cfg['price_per_mtok'], plan['max_output_tokens'], context)
    agent = make_agent(model_cfg, plan, meter)
    started = time.monotonic()
    result = run_trial(row['card'], 'live', agent)
    if agent.error and result['status'] not in ('INFRA_ERROR', 'GRADER_ERROR'):
        result['status'], result['error'] = agent.error['status'], agent.error['reason']
    if meter.stopped:
        result['status'], result['error'] = 'INFRA_ERROR', meter.stop_reason
    if result.get('stop') == 'action_budget' and result['status'] == 'FAIL':
        result['status'], result['error'] = 'AGENT_ERROR', 'action_budget'
    failed = sorted(k for k, v in (result.get('checks') or {}).items() if v is False)
    return dict(case_id=row['case_id'], family=row['family'], trial=trial_no, status=result['status'],
                error=result.get('error'), adapter_error=agent.error, failed_checks=failed,
                checks=result.get('checks'), terminal=result.get('terminal'),
                trace_kinds=[e['kind'] for e in result['trace']], trace=result['trace'],
                refunds_after=(result.get('after') or {}).get('refunds'),
                preambles=getattr(agent, 'preambles', []),
                requests=meter.dispatched, attempted_requests=agent.requests, provider_tool_calls=agent.tool_calls,
                served_models=sorted({s for s in meter.served if s}),
                usage=agent.usage, request_latency_seconds=[round(x, 4) for x in meter.latencies],
                task_seconds=round(time.monotonic() - started, 4)), meter.stopped


def summarise(trials, scheduled):
    counts = Counter(t['status'] for t in trials)
    counts['MISSING'] += scheduled - len(trials)
    passed = counts.get('PASS', 0)
    scored = passed + counts.get('FAIL', 0)
    lat = sorted(x for t in trials for x in t['request_latency_seconds'])
    def pct(q):
        return None if not lat else lat[min(len(lat) - 1, int(q * (len(lat) - 1) + 0.5))]
    return dict(scheduled=scheduled, counts={k: v for k, v in counts.items() if v},
                trial_weighted_success=None if not scheduled else f'{passed}/{scheduled}',
                measured_only_success=None if not scored else f'{passed}/{scored}',
                failure_reasons=dict(Counter(t['error'] or ','.join(t['failed_checks']) or 'none'
                                             for t in trials if t['status'] != 'PASS')),
                served_models=sorted({s for t in trials for s in t['served_models']}),
                requests=sum(t['requests'] for t in trials),
                request_latency_p50=pct(0.5), request_latency_p90=pct(0.9))


def markdown(report):
    out = [f"# Live run: {report['plan']['name']}", '',
           f"Mode: **{report['mode']}** · plan SHA-256 `{report['plan_sha256']}` · started {report['started_utc']}", '',
           '## Predictions (frozen before the run)', '',
           f"- Expected pass rate: {report['plan']['predictions']['expected_pass_rate']}",
           f"- Expected most common failure: {report['plan']['predictions']['expected_most_common_failure']}", '',
           '## Results', '',
           '| Provider | Requested model | Served model | Scheduled | Pass | Fail | Errors | Missing | Requests | p50 latency (s) |',
           '|---|---|---|---|---|---|---|---|---|---|']
    for r in report['runs']:
        s, c = r['summary'], r['summary']['counts']
        errors = sum(v for k, v in c.items() if k not in ('PASS', 'FAIL', 'MISSING'))
        out.append(f"| {r['provider']} | {r['requested_model']} | {', '.join(s['served_models']) or 'unknown'} | "
                   f"{s['scheduled']} | {c.get('PASS', 0)} | {c.get('FAIL', 0)} | {errors} | {c.get('MISSING', 0)} | "
                   f"{s['requests']} | {s['request_latency_p50']} |")
    b = report['budget']
    out += ['', f"Spend: {b['settled']} {b['currency']} settled of a {b['ceiling']} ceiling; "
            f"{b['held_for_unknown_usage']} held for {b['unknown_usage_requests']} request(s) with unknown usage. "
            f"Total {'known' if b['total_known'] else 'NOT known'}.", '',
            'Reservation is a byte-based estimate, not a provider billing guarantee. '
            f"Reservation exceeded: {b['reservation_exceeded']}. Dry-run amounts are simulated, not spend.",
            '', '## Trials that did not pass', '']
    for r in report['runs']:
        for t in r['trials']:
            if t['status'] != 'PASS':
                out.append(f"- **{r['requested_model']}** `{t['case_id']}` ({t['family']}): {t['status']}"
                           f" · {t['error'] or 'failed ' + ', '.join(t['failed_checks'])}"
                           f" · path {' > '.join(t['trace_kinds']) or 'none'}")
    out += ['', 'Read the capture file for the full request and response of each trial before writing it up.']
    return '\n'.join(out) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--plan', required=True)
    ap.add_argument('--out', required=True, help='new directory for capture.jsonl, report.json and summary.md')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true', help='offline fake providers; no network, no spend')
    mode.add_argument('--authorise-live', action='store_true', help='send real requests with conditional local budget admission (not a billing guarantee)')
    ap.add_argument('--dry-fault', choices=['fenced', 'preamble'], help='dry run only: inject a realistic response quirk')
    a = ap.parse_args(argv)

    raw = Path(a.plan).read_bytes()
    try:
        plan = json.loads(raw, object_pairs_hook=strict_object)
    except (ValueError, UnicodeError):
        raise SystemExit('Invalid plan JSON (duplicate members are forbidden).') from None
    validate_plan(plan)
    rows = select_rows(plan['tasks'])
    scheduled = len(rows) * plan['trials_per_task']
    if not (a.dry_run or a.authorise_live):
        print(json.dumps(dict(plan=plan['name'], scheduled_per_model=scheduled, models=[m['model'] for m in plan['models']],
                              ceiling=f"{plan['ceiling']} {plan['currency']}", sent=0)))
        print('No request sent. Add --dry-run to rehearse offline or --authorise-live to run.')
        return 2
    if a.dry_fault and not a.dry_run:
        raise SystemExit('--dry-fault applies only to --dry-run')
    if a.authorise_live:
        for m in plan['models']:
            var = 'ANTHROPIC_API_KEY' if m['provider'] == 'anthropic' else 'OPENAI_API_KEY'
            if not os.environ.get(var):
                raise SystemExit(f'{var} is not set. No request sent.')

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False, mode=0o700)
    (out / 'plan.json').write_bytes(raw)
    capture = Capture(out / 'capture.jsonl')
    budget = Budget(plan['ceiling'], plan['currency'])
    report = dict(schema=SCHEMA, mode='dry-run' if a.dry_run else 'live', dry_fault=a.dry_fault,
                  plan=plan, plan_sha256=hashlib.sha256(raw).hexdigest(),
                  dataset_sha256=hashlib.sha256(DATASET.read_bytes()).hexdigest(),
                  started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), runs=[])
    stopped = False
    for model_cfg in plan['models']:
        trials = []
        for row in rows:
            for n in range(1, plan['trials_per_task'] + 1):
                if stopped:
                    trials.append(dict(case_id=row['case_id'], family=row['family'], trial=n,
                                       status='MISSING', error='run_stopped', failed_checks=[],
                                       trace_kinds=[], served_models=[], requests=0,
                                       request_latency_seconds=[]))
                    continue
                dry = (a.dry_fault or '') if a.dry_run else None
                trial, stopped = run_one(row, n, model_cfg, plan, budget, capture, dry)
                trials.append(trial)
                print(f"{model_cfg['model']:28s} {row['case_id']} #{n}: {trial['status']}"
                      f"{' (' + str(trial['error']) + ')' if trial['error'] else ''}", flush=True)
        report['runs'].append(dict(provider=model_cfg['provider'], requested_model=model_cfg['model'],
                                   price_per_mtok=model_cfg['price_per_mtok'], price_source=model_cfg['price_source'],
                                   summary=summarise(trials, scheduled), trials=trials))
    capture.close()
    report['budget'] = budget.summary()
    report['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    (out / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    (out / 'summary.md').write_text(markdown(report))
    print(f"\nWrote {out/'report.json'}, {out/'summary.md'} and {out/'capture.jsonl'}")
    print(json.dumps(report['budget']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
