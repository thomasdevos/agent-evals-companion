"""Deterministic demonstration; JSON output is synthetic, not a deployment log."""
import argparse
import copy
import json
import rollout as r


def run(mode):
    state=r.initial();transitions=[];packets=[]
    for day,target in zip(range(20,24),r.STAGES[1:]):
        packet=r.evidence(day)
        a=r.approval(state,packet,target,day,accepted=mode!='reject')
        before=copy.deepcopy(state)
        if mode=='missing':packet['sentinel'].pop()
        try:
            state,result=r.advance(state,packet,a,day)
        except ValueError as exc:
            if state!=before:raise RuntimeError('rejected operation changed state')
            return dict(synthetic=True,decision='REJECT',reason=str(exc),state=state,deployment_changes=0),2
        transitions.append(dict(approval=a,result=result,state=copy.deepcopy(state)))
        packets.append(packet)
    stopped=r.rollback(state,24,'INCIDENT',r.OWNER)
    return dict(synthetic=True,transitions=transitions,evidence=packets,rollback=stopped,
                migration=r.migration(24,r.CANDIDATE,r.CANDIDATE,True,True,True),
                deployment_changes=0,committed_effects_unchanged=state['committed_effects']==stopped['committed_effects']),0


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['normal','reject','missing']);a=p.parse_args()
    result,code=run(a.mode);print(json.dumps(result,indent=2,allow_nan=False));return code

if __name__=='__main__':raise SystemExit(main())
