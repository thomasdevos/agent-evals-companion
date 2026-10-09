"""Synthetic envelopes, real local SQLite execution. No model or network calls."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from native import Conversation, SQLiteExecutor, ContractError, MODEL, canonical, require


def envelope(provider, final=False):
    u = dict(input_tokens=10, output_tokens=5)
    if provider == 'responses':
        u.update(total_tokens=15, input_tokens_details=dict(cached_tokens=4, cache_write_tokens=0),
                 output_tokens_details=dict(reasoning_tokens=2))
        items = [dict(type='message', id='msg-final', role='assistant',
                      content=[dict(type='output_text', text='The saved result is available.')])] if final else [
            dict(type='reasoning', id='reason-1', summary=[], encrypted_content='synthetic-opaque-item'),
            dict(type='function_call', id='item-1', call_id='call-1', name='refund',
                 arguments=canonical(dict(order_id='A100', amount_pence=4200))),
            dict(type='function_call', id='item-2', call_id='call-2', name='read',
                 arguments=canonical(dict(text='Read the committed ledger.')))]
        return dict(id='response-final' if final else 'response-1', model=MODEL, status='completed', output=items, usage=u)
    u.update(cache_creation_input_tokens=3, cache_read_input_tokens=4,
             cache_creation=dict(ephemeral_1h_input_tokens=1, ephemeral_5m_input_tokens=2),
             output_tokens_details=dict(thinking_tokens=2))
    items = [dict(type='text', text='The saved result is available.')] if final else [
        dict(type='text', text='I will record the refund, then read the ledger.'),
        dict(type='tool_use', id='call-1', name='refund', input=dict(order_id='A100', amount_pence=4200)),
        dict(type='text', text='The read follows the write.'),
        dict(type='tool_use', id='call-2', name='read', input=dict(text='Read the committed ledger.'))]
    return dict(id='message-final' if final else 'message-1', model=MODEL, type='message', role='assistant',
                stop_reason='end_turn' if final else 'tool_use', content=items, usage=u)


def run(provider, malformed=False):
    c = Conversation(provider, 'Synthetic task: refund A100, then inspect the ledger.')
    first = c.request()
    response = envelope(provider)
    if malformed:
        if provider == 'messages':
            response['content'][-1]['id'] = 'call-1'
        else:
            response['output'][-1]['call_id'] = 'call-1'
    # Whole envelope validation precedes even fixture construction in this demo.
    c.accept(response)
    with tempfile.TemporaryDirectory(prefix='native-demo-') as directory:
        executor = SQLiteExecutor(Path(directory) / 'fixture.sqlite')
        results = c.execute(executor)
        for result in results:
            require(json.loads(result['output'])['refunds'] == [['A100', 4200]], 'missing_committed_refund')
        second = c.request()
        c.accept(envelope(provider, final=True))
        return dict(provenance='synthetic-envelopes-real-local-sqlite', provider=provider,
                    requests=[first, second], results=results, usage=c.usage_records(),
                    executor_calls=executor.calls, model_cost=None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', choices=['responses', 'messages'], default='messages')
    parser.add_argument('--malformed', action='store_true')
    args = parser.parse_args()
    try:
        print(canonical(run(args.provider, args.malformed)))
        return 0
    except ContractError as exc:
        print(canonical(dict(status='BLOCKED', error=str(exc))))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
