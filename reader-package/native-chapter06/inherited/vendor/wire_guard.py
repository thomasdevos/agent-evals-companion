"""Chapter 6 guard around the unchanged Chapter 5 Responses adapter.

The inherited parser uses last-key-wins JSON. Validate all embedded JSON before
its batch parser sees any response; do not monkeypatch shared dependencies.
"""
import json
from chapter05.harness import ProviderAgent


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite JSON')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


class GuardedProviderAgent(ProviderAgent):
    def __init__(self, transport, **kwargs):
        def guarded(payload, timeout):
            response = transport(payload, timeout)
            try:
                if type(response) is dict and response.get('status') == 'completed':
                    output = response['output']
                    for item in output:
                        if item['type'] == 'function_call':
                            strict_json(item['arguments'])
                    messages = [i for i in output if i['type'] == 'message']
                    if messages:
                        text = ''.join(c['text'] for m in messages for c in m['content'] if c['type'] == 'output_text')
                        strict_json(text)
            except (ValueError, TypeError, KeyError):
                self.fail('AGENT_ERROR', 'malformed_provider_response')
            return response
        super().__init__(guarded, **kwargs)
