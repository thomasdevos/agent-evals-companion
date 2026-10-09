"""Offline currency admission through the unchanged cassette executor."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import cassettes as c
from capture_store import MoneyBudget

CONFIG = dict(ceiling=20, attempts=8, input_rate=1, output_rate=2,
              input_limit=1000, output_limit=512, currency='GBP',
              price_source='hypothetical-teaching-only')

class Stop(ValueError):
    pass

class PreflightStop(Stop):
    """A rejection known to precede executor construction."""
    pass

def configured(config):
    if type(config) is not dict or set(config) != set(CONFIG):
        raise Stop('missing_or_invalid_explicit_configuration')
    values = deepcopy(config)
    if values.pop('price_source') != 'hypothetical-teaching-only':
        raise Stop('hypothetical_price_provenance_required')
    return MoneyBudget(**values)

class AdmittedTransport:
    def __init__(self, callback, budget, first):
        self.callback, self.budget, self.first = callback, budget, first
        self.events = []
        self.stop = None

    def __call__(self, payload):
        attempt = self.first
        self.first = None
        if attempt is None:
            try:
                attempt = self.budget.reserve()
            except ValueError:
                self.stop = 'admission_denied'
                raise Stop(self.stop) from None
        event = dict(attempt=attempt, request_sha256=c.digest(payload),
                     reserved_before_callback=self.budget.report()['reserved_minor'])
        self.events.append(event)
        try:
            response = self.callback(payload)
        except Exception as exc:
            self.budget.settle(attempt, None)
            self.stop = 'transport_error_unknown_exposure'
            event['stop'] = self.stop
            event['callback_error'] = dict(type=type(exc).__name__,
                                          module=type(exc).__module__, detail=str(exc))
            # No envelope returned: retain the import-compatible category.
            # Original local fault detail stays in the separate receipt.
            raise OSError('callback_failed_without_response') from exc
        usage = response.get('usage') if type(response) is dict else None
        try:
            self.budget.settle(attempt, usage)
        except ValueError:
            self.stop = 'invalid_or_excess_usage'
        if self.budget.blocked and self.stop is None:
            self.stop = 'unknown_usage'
        event['stop'] = self.stop
        # Return the envelope so the accepted recorder retains its truthful
        # projections. The agent boundary below stops dispatch before action.
        return response

class AdmittedAgent(c.Agent):
    def __init__(self, provider, identity, records, transport):
        super().__init__(provider, identity, records)
        self.admission = transport
    def __call__(self, view):
        if self.admission.stop:
            raise Stop(self.admission.stop)
        if not self.queue and self.admission.first is None:
            try:
                self.admission.first = self.admission.budget.reserve()
            except ValueError:
                self.admission.stop = 'admission_denied'
                raise Stop('admission_denied') from None
        action = super().__call__(view)
        if self.admission.stop:
            raise Stop(self.admission.stop)
        return action

def execute(card, provider, config, callback=None):
    """One trial, single writer, in-memory ledger. No live transport supplied."""
    effective_config = deepcopy(config)
    try:
        budget = configured(effective_config)
        # This must precede executor construction, SQLite setup and callback.
        first = budget.reserve()
        if provider not in c.ADAPTERS:
            raise Stop('unsupported_provider')
    except ValueError as exc:
        raise PreflightStop(str(exc)) from exc
    callback = callback if callback is not None else c.Authored(provider)
    transport = AdmittedTransport(callback, budget, first)
    identity = dict(experiment_id='currency-offline-v1', case_id='full',
                    trial_id='full:1', trial_index=1,
                    companion_version=c.VERSION, versions=c.versions())
    records = []
    agent = AdmittedAgent(c.ADAPTERS[provider](transport), identity, records, transport)
    result = c.run_trial(card, 'currency-admitted', agent)
    # Validate retained envelopes under the unchanged import contract.
    c.validate_imported(records)
    receipt = dict(schema='hypothetical-budget-receipt-v1',
                   provenance='authored-usage-hypothetical-prices-not-invoice',
                   config=effective_config, rounding='ceil combined minor units per request',
                   calls_sha256=c.digest(records), events=transport.events,
                   stop=transport.stop, accounting=budget.report())
    return dict(result=result, records=records, budget_receipt=receipt)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--provider', choices=c.ADAPTERS, default='messages')
    parser.add_argument('--scenario', choices=['normal','denied','unknown','repaired'], default='normal')
    args = parser.parse_args()
    card = json.loads((c.ROOT/'vendor/chapter02/cards/full.json').read_text())
    config = deepcopy(CONFIG)
    if args.scenario == 'denied': config['ceiling'] = 2
    callback = c.Authored(args.provider, 'unknown' if args.scenario == 'unknown' else None)
    try:
        run = execute(card, args.provider, config, callback)
    except PreflightStop as exc:
        print(c.canonical(dict(stop=str(exc), callback_calls=callback.calls, executor_started=False)))
        return 2
    receipt = run['budget_receipt']
    print(c.canonical(dict(status=run['result']['status'], callback_calls=callback.calls,
                          refunds=run['result']['after']['refunds'], **receipt)))
    return 0 if run['result']['status'] == 'PASS' else 2

if __name__ == '__main__':
    raise SystemExit(main())
