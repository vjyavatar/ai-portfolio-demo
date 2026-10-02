import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from retired_site import attach_retired_routes

class RetirementTests(unittest.TestCase):
    def test_removed_app_and_deep_links(self):
        app=FastAPI(); attach_retired_routes(app)
        client=TestClient(app)
        for path in ['/ruralos','/ruralos/','/ruralos/assets/old.js']:
            self.assertEqual(client.get(path).status_code,410)
        response=client.get('/ruralos/sw.js')
        self.assertEqual(response.status_code,200)
        self.assertIn('registration.unregister()',response.text)
        self.assertIn("k.startsWith('saathi-ruralos-')",response.text)
        self.assertEqual(response.headers['cache-control'],'no-store')
