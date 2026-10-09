"""Literal offline demo, synthetic envelopes and actual local task SQL."""
from copy import deepcopy
from pathlib import Path
import tempfile
from demo import envelope
from native import canonical
from task_session import TaskSession, export, replay, lab


def response(provider, number, call=None):
    r=envelope(provider, final=call is None); r['id']='turn-'+str(number)
    if call is not None:
        args={k:v for k,v in call.items() if k!='kind'}
        item=(dict(type='function_call',id='item-'+str(number),call_id='call-'+str(number),name=call['kind'],arguments=canonical(args))
              if provider=='responses' else dict(type='tool_use',id='call-'+str(number),name=call['kind'],input=args))
        r['output' if provider=='responses' else 'content']=[item]
    return r


def run(directory, provider, card, agent='corrected', calls=None):
    s=TaskSession(Path(directory)/'capture',provider,card)
    try:
        choose=lab.scripted_agent(agent)
        number=0
        while s.executor.outcome is None:
            a=choose(deepcopy(s.executor.view)) if calls is None else calls[number]
            number+=1
            s.turn(lambda req,a=a,n=number: response(provider,n,a))
        s.turn(lambda req: response(provider,number+1))
        s.finish(); export(Path(directory)/'capture',Path(directory)/'export')
        return replay(Path(directory)/'export')
    finally: s.executor.close()

if __name__=='__main__':
    for p in ('responses','messages'):
        for card in ('full','clarify','refuse'):
            with tempfile.TemporaryDirectory() as d:
                print(canonical(dict(provider=p,card=card,**run(d,p,card))))
