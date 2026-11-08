import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skill/astra-flash-orchestrator/scripts'))
from doctor import check_local_catalog
from local_config import SetupError


class CatalogCapability(unittest.TestCase):
    def test_live_check_rejects_v1_missing_and_duplicate_worker_entries(self):
        for entries in ([],[{'id':'worker'}],[{'id':'worker','multi_agent_version':'v1'}],[{'id':'worker','multi_agent_version':'v2'}]*2):
            with self.subTest(entries=entries), patch('urllib.request.build_opener') as opener:
                opener.return_value.open.return_value=io.BytesIO(json.dumps({'data':entries}).encode())
                with self.assertRaisesRegex(SetupError,'native v2'):
                    check_local_catalog('http://127.0.0.1:4202/synthetic','worker')

    def test_live_check_accepts_exact_v2_without_inference(self):
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=io.BytesIO(json.dumps({'data':[{'id':'worker','multi_agent_version':'v2'}]}).encode())
            check_local_catalog('http://127.0.0.1:4202/synthetic','worker')
            request=opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(),'GET')
            self.assertTrue(request.full_url.endswith('/models'))
