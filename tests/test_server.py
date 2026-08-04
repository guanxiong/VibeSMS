import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server.app import create_server


class GatewayServerTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        database = str(Path(self.tempdir.name) / "gateway.db")
        self.server = create_server("127.0.0.1", 0, database, "test-token")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = "http://127.0.0.1:%d" % self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tempdir.cleanup()

    def request(self, path, method="GET", payload=None, token=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Gateway-Token"] = token
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        with urlopen(request, timeout=3) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_health_and_dashboard(self):
        status, payload = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        with urlopen(self.base_url + "/", timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("短信与来电终端", response.read().decode("utf-8"))

    def test_rejects_unauthorized_upload(self):
        with self.assertRaises(HTTPError) as raised:
            self.request("/api/v1/events", "POST", {"sender": "10086", "content": "x"})
        self.assertEqual(raised.exception.code, 401)

    def test_sms_upload_is_idempotent_and_updates_device(self):
        event = {
            "device_id": "SEA-AL10-01",
            "sender": "10086",
            "content": "验证码 123456",
            "received_at": "2026-08-04 10:00:00",
            "sim": "SIM2_中国移动",
            "sub_id": "7",
            "call_type": "未知通话",
            "battery": "72% - AC",
            "network": "WIFI",
        }
        status, first = self.request("/api/v1/events", "POST", event, "test-token")
        self.assertEqual(status, 201)
        self.assertFalse(first["duplicate"])
        status, second = self.request("/api/v1/events", "POST", event, "test-token")
        self.assertEqual(status, 200)
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["event_id"], second["event_id"])

        _, events = self.request("/api/v1/events")
        self.assertEqual(len(events["events"]), 1)
        self.assertEqual(events["events"][0]["event_type"], "sms")
        self.assertEqual(events["events"][0]["sim_slot"], 2)
        _, devices = self.request("/api/v1/devices")
        self.assertEqual(devices["devices"][0]["device_id"], "SEA-AL10-01")

    def test_call_type_is_inferred(self):
        event = {
            "device_mark": "SEA-AL10-01",
            "from": "+8613800000000",
            "content": "联系人：未知号码",
            "receive_time": "2026-08-04 10:01:00",
            "card_slot": "SIM1_中国联通",
            "call_type": "未接来电",
        }
        status, _ = self.request("/api/v1/events", "POST", event, "test-token")
        self.assertEqual(status, 201)
        _, events = self.request("/api/v1/events?type=call")
        self.assertEqual(len(events["events"]), 1)
        self.assertEqual(events["events"][0]["event_type"], "call")
        self.assertEqual(events["events"][0]["sim_slot"], 1)

    def test_normalized_numeric_sim_slot_is_one_based(self):
        event = {
            "event_type": "sms",
            "device_id": "SEA-AL10-01",
            "sender": "10010",
            "content": "余额提醒",
            "received_at": "2026-08-04 10:02:00",
            "sim_slot": 1,
        }
        self.request("/api/v1/events", "POST", event, "test-token")
        _, events = self.request("/api/v1/events")
        self.assertEqual(events["events"][0]["sim_slot"], 1)


if __name__ == "__main__":
    unittest.main()
