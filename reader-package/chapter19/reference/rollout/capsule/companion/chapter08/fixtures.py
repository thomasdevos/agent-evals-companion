"""Authored expected values: no expected answer is computed by the grader."""
from copy import deepcopy
from chapter02.task_lab import load_card

# Literal ledgers and labels, independent of ledger_equal and repaired_grade.
CASES = [
    ('correct', [['A100',4200]], True),
    ('absent', [], False),
    ('wrong_amount', [['A100',4199]], False),
    ('duplicate', [['A100',4200],['A100',4200]], False),
    ('wrong_order', [['B200',4200]], False),
    ('extra_effect', [['A100',4200],['B200',1900]], False),
]

def fixture(ledger=None):
    card = load_card('full')
    before = {'orders':[['A100',4200,'paid'],['B200',1900,'paid']], 'refunds':[]}
    after = deepcopy(before); after['refunds'] = deepcopy([['A100',4200]] if ledger is None else ledger)
    trial = dict(before=before, after=after, trace=[dict(kind='refund',order_id='A100',amount_pence=4200,known_order='A100')],
        terminal=dict(status='completed',reason='full_refund',text='The refund was not processed'),
        status='PASS', checks={k:True for k in ('orders_unchanged','exact_refund_ledger','identity_before_effect','authorised_effects','clarification_useful','terminal_outcome')},
        scoring_eligible=True, checks_role='scoring', trial_id=card['id']+':1', error=None, adapter_error=None)
    row = dict(card=card,case_id=card['id'],family='known-completion',variant_group='known-completion-seed-1',severity='medium')
    return trial,row
