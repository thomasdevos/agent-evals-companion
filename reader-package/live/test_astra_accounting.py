"""Offline documented-schema cache accounting and admission regressions."""
import json
import unittest
from decimal import Decimal
from unittest.mock import patch
from live.test_live_run import live_run as L, plan, run, providers

PRICE = dict(input=10, output=50, cached_input=1, cache_write=12.5)

def usage(i=12000, o=100, read=0, write=12000):
    return dict(input_tokens=i, output_tokens=o, total_tokens=i+o,
                input_tokens_details=dict(cached_tokens=read, cache_write_tokens=write),
                output_tokens_details=dict(reasoning_tokens=o))

class AstraAccounting(unittest.TestCase):
    def test_reproduced_write_undercount(self):
        b = L.Budget(2, 'USD'); hold = b.reserve({'x':'x'*12000}, 512, PRICE)
        self.assertEqual(b.settle(hold, usage(), PRICE), Decimal('0.155'))
        self.assertEqual(b.held, 0)

    def test_disjoint_read_write_and_reasoning(self):
        b = L.Budget(2, 'USD'); h = b.reserve({}, 512, PRICE)
        self.assertEqual(L._tokens(usage(100, 10, 20, 30), PRICE), (50, 10, 20, 30))
        self.assertEqual(b.settle(h, usage(100, 10, 20, 30), PRICE), Decimal('0.001395'))

    def test_invalid_categories_remain_held_and_global_stop(self):
        invalid = []
        for field in ('input_tokens','output_tokens','total_tokens'):
            for val in (True, -1, 1.5, float('nan'), float('inf'), '4', None):
                u=usage(); u[field]=val; invalid.append(u)
        for field in ('cached_tokens','cache_write_tokens','future_tokens'):
            for val in (True, -1, 1.5, float('nan'), float('inf'), '4', None):
                u=usage(); u['input_tokens_details'][field]=val; invalid.append(u)
        for detail in (None, [], 'bad', {'future_tokens':0}):
            u=usage(); u['output_tokens_details']=detail; invalid.append(u)
        invalid += [usage(100,10,60,60), {**usage(), 'future_tokens':0},
                    {**usage(), 'cache_read_input_tokens':1},
                    {**usage(), 'output_tokens_details':{'reasoning_tokens':101}}]
        for u in invalid:
            with self.subTest(usage=u):
                b=L.Budget(2,'USD'); h=b.reserve({},512,PRICE)
                self.assertIsNone(b.settle(h,u,PRICE)); self.assertEqual(b.held,h)
                with self.assertRaises(L.BudgetStop): b.reserve({},512,PRICE)

    def test_old_plan_and_missing_cache_tariffs(self):
        L.validate_plan(plan())
        self.assertIsNone(L._tokens(usage(), {'input':10,'output':50}))
        self.assertEqual(L._tokens(dict(input_tokens=1,output_tokens=2)), (1,2,0,0))

    def test_prices_all_finite_strict_and_paired(self):
        for field in PRICE:
            for bad in (True, 0, -1, float('nan'), float('inf'), '1'):
                p=plan();p['models'][0]['price_per_mtok']={**PRICE,field:bad}
                with self.subTest(field=field,bad=bad), self.assertRaises(SystemExit): L.validate_plan(p)
        p=plan();p['models'][0]['price_per_mtok']=PRICE.copy();L.validate_plan(p)
        del p['models'][0]['price_per_mtok']['cached_input']
        with self.assertRaises(SystemExit):L.validate_plan(p)

    def test_reservation_max_tariff_padding_size_and_ceiling(self):
        payload={'x':'a'};b=L.Budget(2,'USD')
        expected=(Decimal(len(json.dumps(payload).encode())*2+8192)*Decimal('12.5')+Decimal(512)*50)/1000000
        self.assertGreaterEqual(b.reserve(payload,512,PRICE),expected)
        with self.assertRaises(L.BudgetStop): b.reserve({'x':'a'*24000},512,PRICE)
        with self.assertRaises(L.BudgetStop): L.Budget('0.01','USD').reserve(payload,512,PRICE)
        expensive={**PRICE,'cached_input':100}
        self.assertGreater(L.Budget(2,'USD').reserve(payload,512,expensive),expected)

    def test_unknown_category_stops_all_scheduled_slots(self):
        p=plan();p['models']=[dict(provider='openai',model='offline-astra',price_source='offline fixture',price_per_mtok=PRICE)]
        with patch.object(providers.FakeOpenAI,'__call__',return_value={'usage':{**usage(),'new_category':0}}):
            _,r,c=run(p,'--dry-run')
        self.assertEqual(r['runs'][0]['summary']['counts'],{'INFRA_ERROR':1,'MISSING':9})
        self.assertEqual(r['runs'][0]['summary']['requests'],1)
        self.assertEqual([x['event'] for x in c],['intent','response'])

if __name__=='__main__':unittest.main()
