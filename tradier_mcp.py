"""Optional read-only official Tradier MCP transport; no order/account tools.

Wire schema verified by public tools/list on 2026-10-12. Expiry discovery stays
on the existing REST API because the MCP server exposes no expiry-list tool.
"""
import json
import re
import time
from datetime import date

import requests

ENDPOINT = 'https://mcp.tradier.com/mcp'
PROTOCOL = '2025-03-26'
MAX_BYTES = 4_000_000


class TransportError(ValueError):
    """Intentionally contains no upstream text, URLs, or credentials."""


def _decode(raw, content_type, request_id):
    try:
        if content_type.split(';')[0].strip() == 'text/event-stream':
            messages = []
            for block in raw.decode('utf-8').replace('\r\n', '\n').split('\n\n'):
                data = '\n'.join(line[5:].lstrip() for line in block.split('\n') if line.startswith('data:'))
                if data:
                    obj = json.loads(data)
                    if isinstance(obj, dict) and obj.get('id') == request_id:
                        messages.append(obj)
            if len(messages) != 1:
                raise ValueError()
            value = messages[0]
        else:
            value = json.loads(raw)
        if not isinstance(value, dict) or value.get('jsonrpc') != '2.0' or value.get('id') != request_id or 'error' in value or not isinstance(value.get('result'), dict):
            raise ValueError()
        return value['result']
    except Exception:
        raise TransportError('Invalid MCP response.') from None


def _post(headers, payload, deadline, notification=False):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TransportError('MCP request deadline exceeded.')
    try:
        with requests.post(ENDPOINT, headers=headers, json=payload,
                           timeout=(min(5, remaining), min(12, remaining)),
                           allow_redirects=False, stream=True) as response:
            if notification and response.status_code in (200, 202, 204):
                return {}, None
            if response.status_code != 200:
                raise ValueError()
            session = response.headers.get('Mcp-Session-Id')
            if session is not None and (len(session) > 512 or not re.fullmatch(r'[\x21-\x7e]+', session)):
                raise ValueError()
            data = bytearray()
            is_sse = response.headers.get('Content-Type', '').split(';')[0].strip() == 'text/event-stream'
            frame = bytearray()
            for chunk in response.iter_content(1 if is_sse else 16384):
                data.extend(chunk)
                if len(data) > MAX_BYTES or time.monotonic() > deadline:
                    raise ValueError()
                if is_sse:
                    frame.extend(chunk)
                    if frame.endswith(b'\n\n') or frame.endswith(b'\r\n\r\n'):
                        text = frame.decode('utf-8').replace('\r\n', '\n')
                        value = '\n'.join(line[5:].lstrip() for line in text.split('\n') if line.startswith('data:'))
                        if value:
                            envelope = json.loads(value)
                            if isinstance(envelope, dict) and envelope.get('id') == payload['id']:
                                return _decode(bytes(frame), 'text/event-stream', payload['id']), session
                        frame.clear()
            return _decode(bytes(data), response.headers.get('Content-Type', ''), payload['id']), session
    except Exception:
        raise TransportError('Tradier MCP request failed.') from None


def _schema_supported(result):
    if not isinstance(result, dict) or not isinstance(result.get('tools'), list):
        return False
    candidates = [t for t in result.get('tools', []) if isinstance(t, dict) and t.get('name') == 'get_options_chain']
    if len(candidates) != 1:
        return False
    schema = candidates[0].get('inputSchema') or {}
    if not isinstance(schema, dict):
        return False
    props = schema.get('properties') or {}
    if not isinstance(props, dict) or not isinstance(schema.get('required'), list) or not all(isinstance(k, str) for k in schema['required']):
        return False
    return (schema.get('type') == 'object' and
            set(schema.get('required', [])) == {'symbol', 'expiration', 'greeks'} and
            set(props) == {'symbol', 'expiration', 'greeks'} and
            all(isinstance(p, dict) and p.get('type') == 'string' for p in props.values()))


def _market_payload(result):
    if result.get('isError'):
        raise TransportError('MCP tool returned an error.')
    payload = result.get('structuredContent')
    if payload is None:
        content = result.get('content')
        if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict) or content[0].get('type') != 'text':
            raise TransportError('Unrecognized MCP market response.')
        try:
            payload = json.loads(content[0]['text'])
        except Exception:
            raise TransportError('Unrecognized MCP market response.') from None
    # Accept only the existing Tradier REST data envelope. Never interpret prose,
    # prices calculated by an LLM, alternative wrappers, or a provider error.
    if not isinstance(payload, dict) or not isinstance(payload.get('options'), dict) or not isinstance(payload['options'].get('option'), (list, dict)):
        raise TransportError('Unrecognized MCP market response.')
    return payload


def options_chain(token, symbol, expiration):
    if not isinstance(token, str) or not token or len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise TransportError('Invalid provider credentials.')
    if not re.fullmatch(r'[A-Z][A-Z0-9.]{0,14}', symbol):
        raise TransportError('Invalid symbol.')
    try:
        if date.fromisoformat(expiration).isoformat() != expiration:
            raise ValueError()
    except Exception:
        raise TransportError('Invalid expiration.') from None
    headers = {'API_KEY': token, 'PAPER_TRADING': 'false',
               'Accept': 'application/json, text/event-stream', 'Content-Type': 'application/json'}
    deadline = time.monotonic() + 15
    result, session = _post(headers, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
        'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'celesys-readonly-options', 'version': '1.0'}}}, deadline)
    if result.get('protocolVersion') != PROTOCOL or not isinstance(result.get('capabilities', {}).get('tools'), dict):
        raise TransportError('Unsupported MCP protocol.')
    headers['MCP-Protocol-Version'] = PROTOCOL
    if session:
        headers['Mcp-Session-Id'] = session
    _post(headers, {'jsonrpc': '2.0', 'method': 'notifications/initialized'}, deadline, notification=True)
    listing, _ = _post(headers, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}}, deadline)
    if not _schema_supported(listing):
        raise TransportError('MCP options schema changed; adapter review required.')
    result, _ = _post(headers, {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {
        'name': 'get_options_chain', 'arguments': {'symbol': symbol, 'expiration': expiration, 'greeks': 'true'}}}, deadline)
    return _market_payload(result)
