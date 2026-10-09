import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
from first_eval import create_fixture, snapshot

def demonstration(shared=False):
    with tempfile.TemporaryDirectory() as d:
        first=Path(d)/'first.sqlite'; create_fixture(first)
        with closing(sqlite3.connect(first)) as db:
            db.execute('INSERT INTO refunds(order_id,amount_pence) VALUES (?,?)',('A100',4200)); db.commit()
        second=first if shared else Path(d)/'second.sqlite'
        if not shared: create_fixture(second)
        before=snapshot(second)
        # Second candidate deliberately does nothing.
        after=snapshot(second)
        return dict(shared=shared,second_before=before,second_after=after,
                    misleading_final_state_pass=after['refunds']==[['A100',4200]],
                    isolation_ok=before['refunds']==[])

def main():
    p=argparse.ArgumentParser(); p.add_argument('--shared',action='store_true'); a=p.parse_args()
    r=demonstration(a.shared); print(json.dumps(r,sort_keys=True)); return 0 if r['isolation_ok'] else 1
if __name__=='__main__': raise SystemExit(main())
