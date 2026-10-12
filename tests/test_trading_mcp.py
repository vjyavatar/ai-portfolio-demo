import json
import unittest
from unittest.mock import patch
import tradier_mcp as m

SCHEMA={'tools':[{'name':'get_options_chain','inputSchema':{'type':'object','properties':{k:{'type':'string'} for k in ('symbol','expiration','greeks')},'required':['symbol','expiration','greeks']}}]}
PAYLOAD={'options':{'option':[{'symbol':'SPY270115C00500000'}]}}

class Response:
    def __init__(self,data=b'',status=200,headers=None,hold=False):
        self.data=data;self.status_code=status;self.headers=headers or {'Content-Type':'application/json'};self.hold=hold
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def iter_content(self,size):
        for i in range(0,len(self.data),size):yield self.data[i:i+size]
        if self.hold:raise AssertionError('Client waited past completed SSE frame')

def response(i,result):return Response(json.dumps({'jsonrpc':'2.0','id':i,'result':result}).encode())

class MCPTests(unittest.TestCase):
    def test_full_readonly_session(self):
        sequence=[response(1,{'protocolVersion':m.PROTOCOL,'capabilities':{'tools':{}}}),Response(status=202),response(2,SCHEMA),response(3,{'content':[{'type':'text','text':json.dumps(PAYLOAD)}]})]
        with patch.object(m.requests,'post',side_effect=sequence) as post:
            self.assertEqual(m.options_chain('secret','SPY','2027-01-15'),PAYLOAD)
        calls=post.call_args_list
        self.assertEqual(len(calls),4)
        for c in calls:
            self.assertEqual(c.args[0],m.ENDPOINT);self.assertFalse(c.kwargs['allow_redirects']);self.assertTrue(c.kwargs['stream'])
            self.assertEqual(c.kwargs['headers']['API_KEY'],'secret')
        params=calls[-1].kwargs['json']['params']
        self.assertEqual(params,{'name':'get_options_chain','arguments':{'symbol':'SPY','expiration':'2027-01-15','greeks':'true'}})
    def test_sse_does_not_wait_for_eof(self):
        data=b': ping\n\ndata: {"jsonrpc":"2.0","id":3,"result":{"content":[]}}\n\n'
        with patch.object(m.requests,'post',return_value=Response(data,headers={'Content-Type':'text/event-stream'},hold=True)):
            result,_=m._post({}, {'id':3},m.time.monotonic()+10)
        self.assertEqual(result,{'content':[]})
    def test_redirect_denied_and_sanitized(self):
        with patch.object(m.requests,'post',return_value=Response(b'secret',302)):
            with self.assertRaisesRegex(m.TransportError,'^Tradier MCP request failed.$'):m._post({}, {'id':1},m.time.monotonic()+10)
    def test_network_error_sanitized(self):
        with patch.object(m.requests,'post',side_effect=ValueError('secret')):
            with self.assertRaisesRegex(m.TransportError,'^Tradier MCP request failed.$'):m._post({}, {'id':1},m.time.monotonic()+10)
    def test_oversize(self):
        with patch.object(m,'MAX_BYTES',5),patch.object(m.requests,'post',return_value=Response(b'123456')):
            with self.assertRaises(m.TransportError):m._post({}, {'id':1},m.time.monotonic()+10)
    def test_bad_session(self):
        with patch.object(m.requests,'post',return_value=Response(headers={'Mcp-Session-Id':'x\r\ny'})):
            with self.assertRaises(m.TransportError):m._post({}, {'id':1},m.time.monotonic()+10)
    def test_schema_change_rejected(self):
        self.assertTrue(m._schema_supported(SCHEMA))
        self.assertFalse(m._schema_supported({'tools':[]}))
        changed=json.loads(json.dumps(SCHEMA));changed['tools'][0]['inputSchema']['properties']['greeks']['type']='boolean'
        self.assertFalse(m._schema_supported(changed))
    def test_invalid_market_payloads(self):
        for value in [{'isError':True},{'content':['bad']},{'content':[{'type':'text','text':'buy now'}]},{'structuredContent':{'options':[]}}, {'structuredContent':{'options':{'option':None}}}]:
            with self.subTest(value=value),self.assertRaises(m.TransportError):m._market_payload(value)
        self.assertEqual(m._market_payload({'structuredContent':PAYLOAD}),PAYLOAD)
    def test_invalid_args_never_network(self):
        with patch.object(m.requests,'post') as post:
            for token,symbol,expiry in [('a\nb','SPY','2027-01-15'),('x','SPY&bad','2027-01-15'),('x','SPY','bad')]:
                with self.assertRaises(m.TransportError):m.options_chain(token,symbol,expiry)
            post.assert_not_called()
    def test_rpc_mismatch_error_rejected(self):
        for raw in [b'{}',b'{"jsonrpc":"2.0","id":4,"result":{}}',b'{"jsonrpc":"2.0","id":3,"error":{"message":"secret"}}']:
            with self.assertRaises(m.TransportError):m._decode(raw,'application/json',3)

if __name__=='__main__':unittest.main()
