"""Offline typed subset, not a provider client. No transport exists here."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'inherited'))
from cassettes import MODEL, TOOLS, ContractError, canonical
from wire_guard import strict_json
from first_eval import create_fixture, snapshot, refund_once, CASE


def require(ok, message):
    if not ok:
        raise ContractError(message)


def obj(value, required, optional=()):
    require(type(value) is dict, 'object_type')
    require(set(required) <= set(value) <= set(required) | set(optional), 'object_fields')


def text(value):
    require(type(value) is str and bool(value.strip()), 'text_type')
    try:
        value.encode('utf-8')
    except UnicodeError as exc:
        raise ContractError('text_encoding') from exc


def count(value):
    require(type(value) is int and value >= 0, 'token_integer')
    return value


def usage(provider, raw):
    """Strict supported categories; null/missing/unknown categories stop admission."""
    require(provider in ('responses', 'messages'), 'provider')
    common = {'input_tokens', 'output_tokens'}
    if provider == 'responses':
        obj(raw, common | {'total_tokens'}, {'input_tokens_details', 'output_tokens_details'})
        inp, out = count(raw['input_tokens']), count(raw['output_tokens'])
        require(count(raw['total_tokens']) == inp + out, 'usage_total')
        details = raw.get('input_tokens_details')
        cats = {'input_total': inp, 'output_total': out}
        if details is not None:
            obj(details, (), {'cached_tokens', 'cache_write_tokens'})
            for key, value in details.items():
                require(count(value) <= inp, 'input_subset')
                cats[key] = value
        # Do not infer that separate cache subsets are disjoint.
        reasoning_key = 'reasoning_tokens'
        total = inp + out
    else:
        obj(raw, common | {'cache_creation_input_tokens', 'cache_read_input_tokens'},
            {'cache_creation', 'output_tokens_details'})
        inp, out = count(raw['input_tokens']), count(raw['output_tokens'])
        created, read = count(raw['cache_creation_input_tokens']), count(raw['cache_read_input_tokens'])
        cats = dict(input_uncached=inp, cache_creation=created, cache_read=read, output_total=out)
        if 'cache_creation' in raw:
            d = raw['cache_creation']
            obj(d, {'ephemeral_1h_input_tokens', 'ephemeral_5m_input_tokens'})
            require(sum(count(v) for v in d.values()) == created, 'cache_breakdown')
            cats['cache_creation_by_ttl'] = deepcopy(d)
        total = inp + created + read + out
        reasoning_key = 'thinking_tokens'
    if 'input_tokens_details' in raw:
        require(raw['input_tokens_details'] is not None, 'unknown_input_details')
    if 'output_tokens_details' in raw:
        d = raw['output_tokens_details']
        obj(d, {reasoning_key})
        require(count(d[reasoning_key]) <= out, 'reasoning_subset')
        cats[reasoning_key] = d[reasoning_key]
    return dict(schema='native-usage-subset-v1', provider=provider, raw=deepcopy(raw),
                categories=cats, total_tokens=total, model_cost=None, tariff=None)


def action(name, arguments):
    text(name)
    require(name in ('refund', 'read'), 'unsupported_tool')
    if name == 'refund':
        obj(arguments, {'order_id', 'amount_pence'})
        text(arguments['order_id'])
        require(type(arguments['amount_pence']) is int, 'refund_integer')
        # This is the inherited fixed support fixture, not general authorisation.
        require(arguments['order_id'] == CASE['order_id'] and
                arguments['amount_pence'] == CASE['amount_pence'], 'fixture_authority')
    else:
        obj(arguments, {'text'})
        text(arguments['text'])
    return dict(kind=name, **deepcopy(arguments))


class Conversation:
    """Single-process reducer with detached state and complete result barriers."""
    def __init__(self, provider, prompt, action_validator=action, tools=None):
        self._action_validator = action_validator
        self._tools = tools
        require(type(provider) is str and provider in ('responses', 'messages'), 'provider')
        text(prompt)
        self.provider = provider
        self._history = [dict(role='user', content=prompt)]
        self._pending = []
        self._seen = set()
        self._response_ids = set()
        self._awaiting = False
        self._closed = False
        self._fault = False
        self._usage = []

    def request(self):
        require(not self._fault and not self._closed and not self._pending and not self._awaiting,
                'request_barrier')
        tools = deepcopy(self._tools) if self._tools is not None else [deepcopy(t) for t in TOOLS if t['name'] in ('refund', 'read')]
        if self.provider == 'responses':
            result = dict(model=MODEL, input=deepcopy(self._history), tools=tools,
                          max_output_tokens=512, store=False)
        else:
            result = dict(model=MODEL, messages=deepcopy(self._history), max_tokens=512,
                          tools=[dict(name=t['name'], description=t['description'],
                                      input_schema=t['parameters']) for t in tools])
        self._awaiting = True
        return result

    def accept(self, response):
        require(self._awaiting and not self._fault, 'response_barrier')
        try:
            r = deepcopy(response)
            common = {'id', 'model', 'usage'}
            if self.provider == 'responses':
                obj(r, common | {'status', 'output'})
                require(type(r['status']) is str and r['status'] == 'completed', 'incomplete_response')
                items = r['output']
            else:
                obj(r, common | {'type', 'role', 'stop_reason', 'content'})
                require(r['type'] == 'message' and r['role'] == 'assistant', 'message_role')
                require(type(r['stop_reason']) is str and r['stop_reason'] in ('tool_use', 'end_turn'), 'stop_reason')
                items = r['content']
            text(r['id']); text(r['model'])
            require(r['id'] not in self._response_ids and r['model'] == MODEL, 'response_identity')
            normalised = usage(self.provider, r['usage'])
            require(type(items) is list and bool(items), 'content_list')
            calls, ids, item_ids, visible = [], set(), set(), False
            for item in items:
                require(type(item) is dict and type(item.get('type')) is str, 'content_type')
                kind = item['type']
                if self.provider == 'responses' and kind == 'function_call':
                    obj(item, {'type', 'id', 'call_id', 'name', 'arguments'})
                    text(item['id']); text(item['arguments'])
                    require(item['id'] not in item_ids, 'duplicate_item_id')
                    item_ids.add(item['id'])
                    cid, args = item['call_id'], strict_json(item['arguments'])
                    call = self._action_validator(item['name'], args)
                elif self.provider == 'messages' and kind == 'tool_use':
                    obj(item, {'type', 'id', 'name', 'input'})
                    cid, call = item['id'], self._action_validator(item['name'], item['input'])
                elif self.provider == 'messages' and kind == 'text':
                    obj(item, {'type', 'text'}); text(item['text']); visible = True
                    continue
                elif self.provider == 'responses' and kind == 'reasoning':
                    obj(item, {'type', 'id', 'summary'}, {'encrypted_content'})
                    text(item['id'])
                    require(item['id'] not in item_ids, 'duplicate_item_id')
                    item_ids.add(item['id'])
                    require(type(item['summary']) is list, 'summary_list')
                    for part in item['summary']:
                        obj(part, {'type', 'text'})
                        require(part['type'] == 'summary_text', 'summary_type'); text(part['text'])
                    if 'encrypted_content' in item:
                        text(item['encrypted_content'])
                    continue
                elif self.provider == 'responses' and kind == 'message':
                    obj(item, {'type', 'id', 'role', 'content'})
                    text(item['id'])
                    require(item['id'] not in item_ids and item['role'] == 'assistant', 'message_identity')
                    item_ids.add(item['id'])
                    require(type(item['content']) is list and bool(item['content']), 'message_content')
                    for part in item['content']:
                        obj(part, {'type', 'text'})
                        require(part['type'] == 'output_text', 'unsupported_text'); text(part['text'])
                    visible = True
                    continue
                else:
                    raise ContractError('unsupported_content')
                text(cid)
                require(cid not in ids and cid not in self._seen, 'duplicate_call_id')
                ids.add(cid); calls.append((cid, call))
            require(bool(calls) or visible, 'empty_turn')
            if self.provider == 'messages':
                require((r['stop_reason'] == 'tool_use') == bool(calls), 'stop_reason_mismatch')
            # Commit only after validating the entire envelope and all calls.
            self._history.extend(deepcopy(items) if self.provider == 'responses' else
                                 [dict(role='assistant', content=deepcopy(items))])
            self._pending = calls
            self._seen.update(ids); self._response_ids.add(r['id'])
            self._usage.append(normalised)
            self._awaiting = False
            self._closed = not calls
            return deepcopy(calls)
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
            self._fault = True
            if isinstance(exc, ContractError):
                raise
            raise ContractError('malformed_envelope') from exc

    def complete(self, results):
        """Trusted executor boundary, not an untrusted receipt import API."""
        require(not self._fault and bool(self._pending), 'result_barrier')
        try:
            require(type(results) is list, 'result_list')
            found = {}
            for result in results:
                obj(result, {'call_id', 'is_error', 'output'})
                text(result['call_id']); text(result['output'])
                require(type(result['is_error']) is bool, 'result_boolean')
                require(result['call_id'] not in found, 'duplicate_result')
                found[result['call_id']] = deepcopy(result)
            require(set(found) == {cid for cid, _ in self._pending}, 'incomplete_or_foreign_results')
            ordered = [found[cid] for cid, _ in self._pending]
            if self.provider == 'responses':
                self._history.extend(dict(type='function_call_output', call_id=r['call_id'],
                                          output=canonical(dict(is_error=r['is_error'], result=r['output'])))
                                     for r in ordered)
            else:
                self._history.append(dict(role='user', content=[dict(type='tool_result',
                    tool_use_id=r['call_id'], content=r['output'], is_error=r['is_error']) for r in ordered]))
            self._pending = []
        except (ValueError, TypeError, KeyError) as exc:
            self._fault = True
            if isinstance(exc, ContractError):
                raise
            raise ContractError('malformed_results') from exc

    def execute(self, executor):
        require(not self._fault and bool(self._pending), 'execution_barrier')
        results = []
        try:
            for cid, call in deepcopy(self._pending):
                output = executor(call)
                obj(output, {'is_error', 'output'})
                require(type(output['is_error']) is bool, 'result_boolean'); text(output['output'])
                results.append(dict(call_id=cid, **output))
            self.complete(results)
            return deepcopy(results)
        except Exception:
            # A failed/incomplete executor result cannot admit another request or effect.
            self._fault = True
            raise

    def usage_records(self):
        return deepcopy(self._usage)


class SQLiteExecutor:
    """Uses the unchanged Chapter 1 commit helper and read-only snapshot."""
    def __init__(self, path):
        self.path = Path(path)
        create_fixture(self.path)
        self.calls = 0

    def __call__(self, call):
        require(type(call) is dict and 'kind' in call, 'action_object')
        a = action(call['kind'], {k: v for k, v in call.items() if k != 'kind'})
        self.calls += 1
        if a['kind'] == 'refund':
            db = sqlite3.connect(self.path)
            try:
                refund_once(db, a)
            except ValueError as exc:
                return dict(is_error=True, output=canonical(dict(error=str(exc))))
            finally:
                db.close()
        # Read committed state from a distinct connection, never infer commit from a call.
        return dict(is_error=False, output=canonical(snapshot(self.path)))
