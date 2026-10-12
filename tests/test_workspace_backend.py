import ast
from pathlib import Path
import unittest
from html.parser import HTMLParser

class WorkspaceBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path('api.py').read_text();cls.tree=ast.parse(cls.source)
    def function(self,name):
        return next(n for n in self.tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    def test_main_home_serves_original_unified_app(self):
        node=self.function('home')
        self.assertEqual(node.body[0].value.value.func.id,'legacy_research')
    def test_no_active_broker_functions_credentials_or_http_endpoint(self):
        calls={n.func.id for n in ast.walk(self.tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
        self.assertFalse(any(n.startswith('_upstox') for n in calls))
        self.assertNotIn('api.upstox.com',self.source)
        self.assertNotIn('os.getenv("UPSTOX',self.source)
        node=self.function('retired_broker_connection')
        self.assertEqual(len(node.decorator_list),4)
        for d in node.decorator_list:self.assertTrue(any(k.arg=='status_code' and k.value.value==410 for k in d.keywords))
    def test_india_scanner_uses_exchange_and_skips_absent_volume(self):
        text=ast.get_source_segment(self.source,self.function('_options_setup_india_nse'))
        self.assertIn('await nse_options(sym)',text)
        self.assertIn('if total_vol <= 0:',text)
        self.assertNotIn('REAL-TIME',text)
    def test_sensex_not_sent_to_nse_and_unverified_ticket_is_blocked(self):
        self.assertIn('if symbol == "SENSEX":',ast.get_source_segment(self.source,self.function('nse_options')))
        self.assertIn('verified contract multiplier and quote times',self.source)
    def test_homepage_controls_have_unique_ids_and_generated_shell_matches(self):
        class Parser(HTMLParser):
            def __init__(self):super().__init__();self.ids=[]
            def handle_starttag(self,tag,attrs):
                a=dict(attrs)
                if a.get('id'):self.ids.append(a['id'])
        html=Path('index.html').read_text();p=Parser();p.feed(html)
        self.assertEqual(len(p.ids),len(set(p.ids)))
        self.assertIn(Path('static/workspace.html').read_text(),html)
        self.assertIn('href="https://celesys.ai/"',html)
        self.assertTrue(html.rstrip().endswith('</html>'))
    def test_frontend_asset_copy_matches_source(self):
        self.assertEqual(Path('static/app.js').read_bytes(),Path('static/app.min.js').read_bytes())
