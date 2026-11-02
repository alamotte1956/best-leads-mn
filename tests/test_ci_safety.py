import os
import unittest
from unittest.mock import patch
from ci import postgres_concurrency


class CISafetyTests(unittest.TestCase):
    def test_hosted_or_non_test_target_is_rejected_before_any_connection(self):
        for target in ('postgresql://user:dummy@production.example/test_rcusa',
                       'postgresql://user:dummy@127.0.0.1/production',
                       'sqlite:///production.db',
                       'postgresql://user:dummy@127.0.0.1/test_rcusa?host=production.example',
                       'postgresql://user:dummy@127.0.0.1/test_rcusa?dbname=production'):
            with patch.dict(os.environ,{'POSTGRES_TEST_URL':target}),patch('ci.postgres_concurrency.create_engine') as connect:
                with self.assertRaises(ValueError):postgres_concurrency.setUpModule()
                connect.assert_not_called()

    def test_missing_test_database_skips_without_creating_any_connection(self):
        with patch.dict(os.environ,{'POSTGRES_TEST_URL':''}),patch('ci.postgres_concurrency.create_engine') as connect:
            with self.assertRaises(unittest.SkipTest):postgres_concurrency.setUpModule()
            connect.assert_not_called()


    def test_browser_fixture_ignores_hosted_database_and_serves_while_socket_is_idle(self):
        import json
        import socket
        import subprocess
        import sys
        import time
        import urllib.request
        from pathlib import Path
        from concurrent.futures import ThreadPoolExecutor
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
        environment={**os.environ,'CI':'true','RCUSA_BROWSER_FIXTURE':'1','RCUSA_BROWSER_PORT':str(port),
            'DATABASE_URL':'postgresql://synthetic:synthetic@must-not-connect.invalid/production'}
        root=Path(__file__).resolve().parents[1]
        process=subprocess.Popen([sys.executable,str(root/'ci'/'browser_fixture.py')],cwd=root,
            env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        origin=f'http://127.0.0.1:{port}'
        try:
            ready=False
            for _ in range(100):
                if process.poll() is not None:
                    self.fail('Isolated browser fixture failed: '+process.stdout.read()[-2000:])
                try:
                    with urllib.request.urlopen(origin+'/health',timeout=.2) as response:
                        ready=response.status==200
                    if ready:break
                except (OSError,TimeoutError):time.sleep(.05)
            self.assertTrue(ready,'Isolated browser fixture did not become ready.')
            # WebKit can preconnect and leave a socket idle. A single-threaded
            # Werkzeug server would block all other browsers behind that socket.
            with socket.create_connection(('127.0.0.1',port),timeout=2) as idle:
                with urllib.request.urlopen(origin+'/health',timeout=3) as response:
                    self.assertEqual(response.status,200)
                def submit(index):
                    body=json.dumps({'homeowner_name':'Synthetic CI '+str(index),
                        'phone':'6125550199','zip_code':'55401','service_needed':'Mold Remediation'}).encode()
                    request=urllib.request.Request(origin+'/api/leads',data=body,
                        headers={'Content-Type':'application/json'},method='POST')
                    with urllib.request.urlopen(request,timeout=5) as response:
                        self.assertEqual(response.status,201)
                        return json.load(response)['lead_id']
                with ThreadPoolExecutor(max_workers=4) as pool:
                    ids=list(pool.map(submit,range(4)))
                self.assertEqual(len(set(ids)),4)
        finally:
            process.terminate()
            try:process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill();process.communicate(timeout=5)
