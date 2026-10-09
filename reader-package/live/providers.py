"""Provider adapters for the live run.

Anthropic Messages is implemented here. OpenAI Responses reuses Chapter 5's
ProviderAgent unchanged, so both providers face the same executor and grader.
Every transport has the signature transport(payload, timeout) -> dict.
"""
from copy import deepcopy
import json
import os
import time
import urllib.error
import urllib.request

from chapter02.task_lab import scripted_agent
from chapter05.harness import TOOLS, Fault, TransportError

SYSTEM_PROMPT = (
    'Handle this synthetic support task. Use tools for actions. Ask once if identity is missing. '
    'Final response MUST be a JSON object with status completed or refused, reason full_refund '
    'or not_owned, and nonempty text. Do not emit final text alongside tool calls.')

ANTHROPIC_TOOLS = [dict(name=t['name'], description=t['description'],
                        input_schema=deepcopy(t['parameters'])) for t in TOOLS]

RETRYABLE = {408, 409, 429, 500, 502, 503, 504, 529}


class ProviderHTTPError(TransportError):
    """Carries only an HTTP status and the provider's error type, never the body."""
    def __init__(self, status, error_type=None):
        self.status, self.error_type = status, error_type
        super().__init__(f'http_{status}')


def _post(url, payload, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json', **headers})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        # Arbitrary error bodies/types can contain sensitive provider text.
        raise ProviderHTTPError(exc.code) from None
    except Exception:
        raise TransportError('network_or_decode_error') from None


class AnthropicTransport:
    url = 'https://api.anthropic.com/v1/messages'
    def __call__(self, payload, timeout):
        key = os.environ.get('ANTHROPIC_API_KEY')
        if not key:
            raise TransportError('missing_credential')
        return _post(self.url, payload, {'x-api-key': key, 'anthropic-version': '2023-06-01'}, timeout)


class OpenAITransport:
    url = 'https://api.openai.com/v1/responses'
    def __call__(self, payload, timeout):
        key = os.environ.get('OPENAI_API_KEY')
        if not key:
            raise TransportError('missing_credential')
        return _post(self.url, payload, {'Authorization': 'Bearer ' + key}, timeout)


def _check_args(name, args):
    spec = next((t for t in TOOLS if t['name'] == name), None)
    if spec is None or type(args) is not dict or set(args) != set(spec['parameters']['properties']):
        raise ValueError('tool_contract')
    for key, rule in spec['parameters']['properties'].items():
        if type(args[key]) is not (int if rule['type'] == 'integer' else str):
            raise ValueError('tool_contract')
    if name == 'refund' and not 0 < args['amount_pence'] <= 2**63 - 1:
        raise ValueError('tool_contract')
    if name == 'ask' and not args['text'].strip():
        raise ValueError('tool_contract')


class MessagesAgent:
    """Anthropic Messages adapter with the same contract as Chapter 5's ProviderAgent.

    Differences that follow the Messages protocol: text may precede tool_use blocks
    (recorded, not treated as a final answer), and every tool_use id receives a
    tool_result in the next user message before any other content.
    """
    def __init__(self, transport, model, retry=False, requests=8, seconds=120, max_tokens=512):
        self.transport, self.model, self.retry = transport, model, retry
        self.cap, self.deadline, self.max_tokens = requests, time.monotonic() + seconds, max_tokens
        self.messages, self.queue, self.awaiting = [], [], []
        self.requests, self.attempts, self.tool_calls = 0, 0, 0
        self.usage, self.error, self.preambles = [], None, []
        self.call_observation_complete = True
        self.call_ids = set()

    def fail(self, status, reason, provider_code=None):
        self.error = dict(status=status, reason=reason)
        if provider_code is not None:
            self.error['provider_code'] = provider_code
        raise Fault(status, reason)

    def check(self):
        if time.monotonic() >= self.deadline:
            self.fail('INFRA_ERROR', 'local_deadline')

    def __call__(self, view):
        self.check()
        if not self.messages:
            self.messages = [dict(role='user', content=json.dumps(
                {k: view[k] for k in ('request', 'policy', 'orders')}))]
        if self.queue:
            cid, action = self.queue.pop(0)
            self.awaiting.append(cid)
            return action
        if self.awaiting:
            observed = json.dumps(view['trace'])
            self.messages.append(dict(role='user', content=[
                dict(type='tool_result', tool_use_id=cid, content=observed) for cid in self.awaiting]))
            self.awaiting = []
        response = None
        for attempt in range(2 if self.retry else 1):
            self.check()
            if self.requests >= self.cap:
                self.fail('AGENT_ERROR', 'request_budget')
            self.requests += 1
            self.attempts += 1
            payload = dict(model=self.model, max_tokens=self.max_tokens, system=SYSTEM_PROMPT,
                           tools=ANTHROPIC_TOOLS, messages=deepcopy(self.messages))
            try:
                response = self.transport(payload, max(0.001, self.deadline - time.monotonic()))
                self.usage.append(response.get('usage') if isinstance(response, dict) else None)
                break
            except Fault:
                raise
            except ProviderHTTPError as exc:
                self.usage.append(None)
                self.call_observation_complete = False
                last = attempt == (1 if self.retry else 0)
                if exc.status not in RETRYABLE or last:
                    status = 'INFRA_ERROR' if exc.status in RETRYABLE or exc.status >= 500 else 'AGENT_ERROR'
                    self.fail(status, 'provider_http', f'{exc.status}:{exc.error_type}')
            except TransportError:
                self.usage.append(None)
                self.call_observation_complete = False
                if attempt == (1 if self.retry else 0):
                    self.fail('INFRA_ERROR', 'provider_transport')
        self.check()
        try:
            if not isinstance(response, dict) or response.get('type') != 'message':
                raise ValueError()
            stop = response.get('stop_reason')
            if stop == 'max_tokens':
                self.fail('AGENT_ERROR', 'provider_noncompleted')
            if stop == 'refusal':
                self.fail('AGENT_ERROR', 'provider_refusal')
            content = response['content']
            if not isinstance(content, list) or not content:
                raise ValueError()
            uses = [b for b in content if b.get('type') == 'tool_use']
            texts = [b for b in content if b.get('type') == 'text']
            if any(b.get('type') not in ('text', 'tool_use', 'thinking', 'redacted_thinking') for b in content):
                raise ValueError()
            self.tool_calls += len(uses)
            actions = []
            for block in uses:
                cid, name, args = block['id'], block['name'], block['input']
                if not isinstance(cid, str) or not cid or cid in self.call_ids:
                    raise ValueError()
                self.call_ids.add(cid)
                _check_args(name, args)
                actions.append((cid, dict(kind=name, **deepcopy(args))))
            self.messages.append(dict(role='assistant', content=deepcopy(content)))
            if actions:
                if texts:
                    self.preambles.append(''.join(b['text'] for b in texts))
                cid, action = actions[0]
                self.queue = actions[1:]
                self.awaiting.append(cid)
                return action
            final = json.loads(''.join(b['text'] for b in texts))
            if type(final) is not dict or set(final) != {'status', 'reason', 'text'}:
                raise ValueError()
            return dict(kind='finish', **final)
        except Fault:
            raise
        except Exception:
            self.fail('AGENT_ERROR', 'malformed_provider_response')


class FakeAnthropic:
    """Offline stand-in that emits Messages-shaped envelopes from the corrected script.

    fault='fenced' wraps the final JSON in a Markdown code fence and fault='preamble'
    adds text before each tool call; both are common in real responses. Never a recording.
    """
    def __init__(self, fault=None):
        self.fault, self.calls = fault, 0
    def __call__(self, payload, timeout):
        self.calls += 1
        msgs = payload['messages']
        view = json.loads(msgs[0]['content'])
        trace = []
        for m in msgs:
            if m['role'] == 'user' and isinstance(m['content'], list):
                trace = json.loads(m['content'][-1]['content'])
        view['trace'] = trace
        replies = [e for e in trace if e['kind'] == 'user_reply']
        if replies:
            view['request']['order_id'] = replies[-1]['order_id']
        action = scripted_agent('corrected')(view)
        if action['kind'] == 'finish':
            text = json.dumps({k: v for k, v in action.items() if k != 'kind'})
            if self.fault == 'fenced':
                text = '```json\n' + text + '\n```'
            content = [dict(type='text', text=text)]
            stop = 'end_turn'
        else:
            content = [dict(type='tool_use', id=f'toolu_{self.calls}', name=action.pop('kind'), input=action)]
            if self.fault == 'preamble':
                content.insert(0, dict(type='text', text='Let me handle that.'))
            stop = 'tool_use'
        return dict(type='message', role='assistant', model=payload['model'] + '-served', content=content,
                    stop_reason=stop, usage=dict(input_tokens=400 + 60 * len(msgs), output_tokens=60))


class FakeOpenAI:
    """Offline stand-in for Responses envelopes, adding usage and a served model."""
    def __init__(self):
        from chapter05.harness import FixtureTransport
        self.inner = FixtureTransport()
    def __call__(self, payload, timeout):
        response = self.inner(payload, timeout)
        response['model'] = payload['model'] + '-served'
        response['usage'] = dict(input_tokens=400 + 60 * len(payload['input']), output_tokens=60)
        return response
