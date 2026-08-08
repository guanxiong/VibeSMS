import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server.app import create_server, extract_otp


class GatewayServerTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        database = str(Path(self.tempdir.name) / "gateway.db")
        self.server = create_server(
            "127.0.0.1",
            0,
            database,
            "test-token",
            admin_username="admin",
            admin_password="admin-password",
            bootstrap_device_id="SEA-AL10-01",
            offline_seconds=30,
            heartbeat_seconds=60,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = "http://127.0.0.1:%d" % self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tempdir.cleanup()

    def request(
        self, path, method="GET", payload=None, token=None, user_token=None, admin=False
    ):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Gateway-Token"] = token
        if user_token:
            headers["Authorization"] = "Bearer " + user_token
        if admin:
            credentials = base64.b64encode(b"admin:admin-password").decode("ascii")
            headers["Authorization"] = "Basic " + credentials
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        with urlopen(request, timeout=3) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_health_and_public_homepage(self):
        status, payload = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["name"], "VibeSMS")

        with urlopen(self.base_url + "/", timeout=3) as response:
            self.assertEqual(response.status, 200)
            homepage = response.read().decode("utf-8")
        self.assertIn("让你的 Agent", homepage)
        self.assertIn('href="/admin/"', homepage)
        self.assertIn("VibeSMS-0.1.0.apk", homepage)
        self.assertIn('class="keep-together">“短信列表”，</span>', homepage)
        self.assertIn('class="keep-together">号码</span>', homepage)
        self.assertIn('class="keep-together">手机短信。</span>', homepage)
        self.assertIn('href="/apply/"', homepage)
        self.assertIn('href="/activate/"', homepage)
        self.assertIn('data-code-tab="python"', homepage)
        self.assertIn('data-code-tab="skill"', homepage)
        self.assertIn("npx skills add guanxiong/VibeSMS", homepage)
        self.assertIn("gh skill install guanxiong/VibeSMS", homepage)
        self.assertIn('id="skill"', homepage)
        self.assertIn('href="/inbox/"', homepage)
        self.assertIn("申请测试 Key", homepage)
        self.assertNotIn("即将发布", homepage)

        with urlopen(self.base_url + "/site/styles.css", timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(".hero", response.read().decode("utf-8"))

        with urlopen(self.base_url + "/site/og-vibesms.jpg", timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get_content_type(), "image/jpeg")
            self.assertGreater(len(response.read()), 1000)

    def test_public_key_inbox_page_does_not_require_admin_auth(self):
        for path, expected in (
            ("/inbox/", "只看属于"),
            ("/inbox/styles.css", ".login-layout"),
            ("/inbox/app.js", "sessionStorage"),
        ):
            with urlopen(self.base_url + path, timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(expected, response.read().decode("utf-8"))

        inbox_html = (
            Path(__file__).resolve().parents[1]
            / "server"
            / "static"
            / "inbox"
            / "index.html"
        ).read_text(encoding="utf-8")
        self.assertIn('content="noindex,nofollow"', inbox_html)
        self.assertIn("vbs_live_", inbox_html)
        self.assertNotIn("/api/v1/admin", inbox_html)

        with self.assertRaises(HTTPError) as raised:
            self.request("/api/v1/inbox?order=desc", user_token="not-a-key")
        self.assertEqual(raised.exception.code, 401)

    def test_public_request_and_one_time_activation_flow(self):
        for path, expected in (
            ("/apply/", "ACCESS / TEST KEY"),
            ("/apply/styles.css", ".form-card"),
            ("/apply/app.js", "/api/v1/key-requests"),
            ("/activate/", "兑换激活码"),
            ("/activate/app.js", "sessionStorage"),
        ):
            with urlopen(self.base_url + path, timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(expected, response.read().decode("utf-8"))

        status, request = self.request(
            "/api/v1/key-requests",
            "POST",
            {
                "email": "agent@example.com",
                "use_case": "Use my own Android SIM with an Agent.",
                "device_count": "1",
                "contact": "wechat-example",
            },
        )
        self.assertEqual(status, 201)
        self.assertTrue(request["request_id"].startswith("vr_"))

        _, requests = self.request("/api/v1/admin/key-requests", admin=True)
        self.assertEqual(requests["requests"][0]["email"], "agent@example.com")
        self.assertEqual(requests["requests"][0]["status"], "pending")

        status, activation = self.request(
            "/api/v1/admin/activation-codes",
            "POST",
            {"request_id": request["request_id"], "label": "Agent test", "expires_in_days": 14},
            admin=True,
        )
        self.assertEqual(status, 201)
        self.assertTrue(activation["activation_code"].startswith("vba_"))
        self.assertTrue(activation["activation_code_shown_once"])

        _, activation_codes = self.request("/api/v1/admin/activation-codes", admin=True)
        self.assertNotIn("activation_code", activation_codes["activation_codes"][0])
        self.assertEqual(activation_codes["activation_codes"][0]["status"], "available")

        status, redeemed = self.request(
            "/api/v1/activations/redeem",
            "POST",
            {"activation_code": activation["activation_code"], "phone_number": "+8613800012345"},
        )
        self.assertEqual(status, 201)
        self.assertTrue(redeemed["key"].startswith("vbs_live_"))
        self.assertTrue(redeemed["key_shown_once"])

        with self.assertRaises(HTTPError) as raised:
            self.request(
                "/api/v1/activations/redeem",
                "POST",
                {"activation_code": activation["activation_code"], "phone_number": "+8613800012345"},
            )
        self.assertEqual(raised.exception.code, 400)

        _, activation_codes = self.request("/api/v1/admin/activation-codes", admin=True)
        self.assertEqual(activation_codes["activation_codes"][0]["status"], "redeemed")
        self.assertEqual(activation_codes["activation_codes"][0]["key_id"], redeemed["key_id"])

    def test_admin_can_disable_unused_activation_code(self):
        _, activation = self.request(
            "/api/v1/admin/activation-codes",
            "POST",
            {"label": "manual delivery", "expires_in_days": 1},
            admin=True,
        )
        status, disabled = self.request(
            "/api/v1/admin/activation-codes/%s/disable" % activation["activation_id"],
            "POST",
            {},
            admin=True,
        )
        self.assertEqual(status, 200)
        self.assertEqual(disabled["action"], "disable")
        with self.assertRaises(HTTPError) as raised:
            self.request(
                "/api/v1/activations/redeem",
                "POST",
                {"activation_code": activation["activation_code"], "phone_number": "+8613800012345"},
            )
        self.assertEqual(raised.exception.code, 400)

    def test_otp_extraction_prefers_verification_code_over_year(self):
        self.assertEqual(extract_otp("2026-08-08 登录验证码为 482913"), "482913")
        self.assertEqual(extract_otp("Your code is 472 913."), "472913")

    def test_admin_dashboard_requires_auth(self):
        with self.assertRaises(HTTPError) as raised:
            urlopen(self.base_url + "/admin/", timeout=3)
        self.assertEqual(raised.exception.code, 401)
        credentials = base64.b64encode(b"admin:admin-password").decode("ascii")
        request = Request(
            self.base_url + "/admin/", headers={"Authorization": "Basic " + credentials}
        )
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("VibeSMS", response.read().decode("utf-8"))

        with self.assertRaises(HTTPError) as raised:
            urlopen(self.base_url + "/admin/app.js", timeout=3)
        self.assertEqual(raised.exception.code, 401)
        with self.assertRaises(HTTPError) as raised:
            urlopen(self.base_url + "/api/v1/admin/keys", timeout=3)
        self.assertEqual(raised.exception.code, 401)

    def test_admin_sim_slot_only_activates_for_prebinding(self):
        root = Path(__file__).resolve().parents[1] / "server" / "static" / "admin"
        html = (root / "index.html").read_text(encoding="utf-8")
        css = (root / "styles.css").read_text(encoding="utf-8")
        javascript = (root / "app.js").read_text(encoding="utf-8")

        self.assertIn('class="sim-field"', html)
        self.assertIn('aria-describedby="key-sim-help" disabled required', html)
        self.assertIn("由 APK 首次绑定选择", html)
        self.assertIn(".key-form .sim-field", css)
        self.assertIn("function syncSimSlotState()", javascript)
        self.assertIn("simSelect.disabled = !hasPreboundDevice", javascript)

    def test_unknown_public_path_is_not_an_auth_prompt(self):
        with self.assertRaises(HTTPError) as raised:
            urlopen(self.base_url + "/missing", timeout=3)
        self.assertEqual(raised.exception.code, 404)

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

        _, events = self.request("/api/v1/events", admin=True)
        self.assertEqual(len(events["events"]), 1)
        self.assertEqual(events["events"][0]["event_type"], "sms")
        self.assertEqual(events["events"][0]["sim_slot"], 2)
        _, devices = self.request("/api/v1/devices", admin=True)
        self.assertEqual(devices["devices"][0]["device_id"], "SEA-AL10-01")
        self.assertTrue(devices["devices"][0]["online"])

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
        _, events = self.request("/api/v1/events?type=call", admin=True)
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
        _, events = self.request("/api/v1/events", admin=True)
        self.assertEqual(events["events"][0]["sim_slot"], 1)

    def test_heartbeat_updates_device_without_creating_event(self):
        heartbeat = {
            "device_id": "SEA-AL10-01",
            "app_version": "3.5.0",
            "battery": "88%",
            "network": "WIFI",
        }
        status, response = self.request(
            "/api/v1/devices/heartbeat", "POST", heartbeat, "test-token"
        )
        self.assertEqual(status, 200)
        self.assertEqual(response["next_heartbeat_seconds"], 60)
        _, events = self.request("/api/v1/events", admin=True)
        self.assertEqual(events["events"], [])
        _, devices = self.request("/api/v1/devices", admin=True)
        self.assertTrue(devices["devices"][0]["online"])
        self.assertTrue(devices["devices"][0]["last_heartbeat"])

    def test_admin_can_provision_independent_device_token(self):
        status, provisioned = self.request(
            "/api/v1/admin/devices",
            "POST",
            {"device_id": "PIXEL-02", "label": "backup"},
            admin=True,
        )
        self.assertEqual(status, 201)
        self.assertTrue(provisioned["token"])

        event = {
            "device_id": "PIXEL-02",
            "event_type": "sms",
            "sender": "10086",
            "content": "device scoped token",
        }
        status, _ = self.request(
            "/api/v1/events", "POST", event, provisioned["token"]
        )
        self.assertEqual(status, 201)

        event["device_id"] = "SEA-AL10-01"
        with self.assertRaises(HTTPError) as raised:
            self.request("/api/v1/events", "POST", event, provisioned["token"])
        self.assertEqual(raised.exception.code, 401)

        _, credentials = self.request("/api/v1/admin/devices", admin=True)
        self.assertEqual(len(credentials["credentials"]), 2)
        self.assertNotIn("token", credentials["credentials"][0])
        self.assertNotIn("token_hash", credentials["credentials"][0])

    def test_admin_can_issue_list_rotate_and_disable_user_key(self):
        status, issued = self.request(
            "/api/v1/admin/keys",
            "POST",
            {
                "phone_number": "+8613800000001",
                "label": "primary",
                "owner_ref": "panel:user-1",
                "device_id": "SEA-AL10-01",
                "sim_slot": 1,
            },
            admin=True,
        )
        self.assertEqual(status, 201)
        self.assertTrue(issued["key"].startswith("vbs_live_"))

        _, listed = self.request("/api/v1/admin/keys", admin=True)
        self.assertEqual(len(listed["keys"]), 1)
        self.assertEqual(listed["keys"][0]["phone_number"], "+8613800000001")
        self.assertNotIn("key", listed["keys"][0])
        self.assertNotIn("token_hash", listed["keys"][0])

        _, status_payload = self.request(
            "/api/v1/status", user_token=issued["key"]
        )
        self.assertTrue(status_payload["bound"])
        self.assertEqual(status_payload["sim_slot"], 1)

        _, rotated = self.request(
            "/api/v1/admin/keys/%s/rotate" % issued["key_id"],
            "POST",
            {},
            admin=True,
        )
        with self.assertRaises(HTTPError) as raised:
            self.request("/api/v1/status", user_token=issued["key"])
        self.assertEqual(raised.exception.code, 401)
        self.request("/api/v1/status", user_token=rotated["key"])

        self.request(
            "/api/v1/admin/keys/%s/disable" % issued["key_id"],
            "POST",
            {},
            admin=True,
        )
        with self.assertRaises(HTTPError) as raised:
            self.request("/api/v1/status", user_token=rotated["key"])
        self.assertEqual(raised.exception.code, 401)

    def test_user_key_binding_returns_upload_only_device_token(self):
        _, issued = self.request(
            "/api/v1/admin/keys",
            "POST",
            {"phone_number": "+8613900000002", "label": "new terminal"},
            admin=True,
        )
        status, binding = self.request(
            "/api/v1/bindings",
            "POST",
            {"device_id": "PIXEL-02", "sim_slot": 2},
            user_token=issued["key"],
        )
        self.assertEqual(status, 201)
        self.assertTrue(binding["device_token"])
        self.assertTrue(binding["device_token_shown_once"])

        status, repeated = self.request(
            "/api/v1/bindings",
            "POST",
            {"device_id": "PIXEL-02", "sim_slot": 2},
            user_token=issued["key"],
        )
        self.assertEqual(status, 200)
        self.assertTrue(repeated["already_bound"])
        self.assertTrue(repeated["device_token"])
        self.assertNotEqual(repeated["device_token"], binding["device_token"])

        event = {
            "device_id": "PIXEL-02",
            "event_type": "sms",
            "sender": "Example",
            "content": "Your verification code is 472 913",
            "sim_slot": 2,
        }
        with self.assertRaises(HTTPError) as raised:
            self.request(
                "/api/v1/events", "POST", event, token=binding["device_token"]
            )
        self.assertEqual(raised.exception.code, 401)
        self.request(
            "/api/v1/events", "POST", event, token=repeated["device_token"]
        )
        _, inbox = self.request("/api/v1/inbox", user_token=issued["key"])
        self.assertEqual(len(inbox["events"]), 1)
        self.assertEqual(inbox["events"][0]["sender"], "Example")

        _, otp = self.request(
            "/api/v1/otp/wait?after_id=0&timeout=0", user_token=issued["key"]
        )
        self.assertEqual(otp["status"], "received")
        self.assertEqual(otp["code"], "472913")
        _, timeout = self.request(
            "/api/v1/otp/wait?after_id=%d&timeout=0" % otp["cursor"],
            user_token=issued["key"],
        )
        self.assertEqual(timeout["status"], "timeout")

        with self.assertRaises(HTTPError) as raised:
            self.request(
                "/api/v1/events",
                "POST",
                event,
                user_token=issued["key"],
            )
        self.assertEqual(raised.exception.code, 401)

    def test_admin_prebinding_still_allows_first_device_token_exchange(self):
        _, issued = self.request(
            "/api/v1/admin/keys",
            "POST",
            {
                "phone_number": "+8613900000088",
                "device_id": "PREBOUND-08",
                "sim_slot": 1,
            },
            admin=True,
        )
        status, binding = self.request(
            "/api/v1/bindings",
            "POST",
            {"device_id": "PREBOUND-08", "sim_slot": 1},
            user_token=issued["key"],
        )
        self.assertEqual(status, 200)
        self.assertTrue(binding["already_bound"])
        self.assertTrue(binding["device_token"])

    def test_user_keys_are_isolated_by_device_and_sim(self):
        _, sim1_key = self.request(
            "/api/v1/admin/keys",
            "POST",
            {
                "phone_number": "+8613800000011",
                "device_id": "SEA-AL10-01",
                "sim_slot": 1,
            },
            admin=True,
        )
        _, sim2_key = self.request(
            "/api/v1/admin/keys",
            "POST",
            {
                "phone_number": "+8613800000022",
                "device_id": "SEA-AL10-01",
                "sim_slot": 2,
            },
            admin=True,
        )
        for sim_slot, sender in ((1, "SIM-ONE"), (2, "SIM-TWO")):
            self.request(
                "/api/v1/events",
                "POST",
                {
                    "device_id": "SEA-AL10-01",
                    "event_type": "sms",
                    "sender": sender,
                    "content": "code %d2345" % sim_slot,
                    "sim_slot": sim_slot,
                },
                token="test-token",
            )
        self.request(
            "/api/v1/events",
            "POST",
            {
                "device_id": "SEA-AL10-01",
                "event_type": "sms",
                "sender": "SIM-ONE-LATEST",
                "content": "latest code 654321",
                "sim_slot": 1,
            },
            token="test-token",
        )

        _, sim1_inbox = self.request(
            "/api/v1/inbox", user_token=sim1_key["key"]
        )
        _, sim2_inbox = self.request(
            "/api/v1/inbox", user_token=sim2_key["key"]
        )
        _, sim1_latest = self.request(
            "/api/v1/inbox?order=desc", user_token=sim1_key["key"]
        )
        self.assertEqual(
            [event["sender"] for event in sim1_inbox["events"]],
            ["SIM-ONE", "SIM-ONE-LATEST"],
        )
        self.assertEqual(
            [event["sender"] for event in sim1_latest["events"]],
            ["SIM-ONE-LATEST", "SIM-ONE"],
        )
        self.assertEqual([event["sender"] for event in sim2_inbox["events"]], ["SIM-TWO"])

    def test_active_phone_and_binding_cannot_be_claimed_twice(self):
        _, issued = self.request(
            "/api/v1/admin/keys",
            "POST",
            {"phone_number": "+8613700000003"},
            admin=True,
        )
        with self.assertRaises(HTTPError) as raised:
            self.request(
                "/api/v1/admin/keys",
                "POST",
                {"phone_number": "+8613700000003"},
                admin=True,
            )
        self.assertEqual(raised.exception.code, 409)

        _, unbound = self.request(
            "/api/v1/admin/keys",
            "POST",
            {"phone_number": "+8613700000099"},
            admin=True,
        )
        with self.assertRaises(HTTPError) as raised:
            self.request(
                "/api/v1/bindings",
                "POST",
                {"device_id": "PIXEL-99", "sim_slot": 0},
                user_token=unbound["key"],
            )
        self.assertEqual(raised.exception.code, 400)

        self.request(
            "/api/v1/bindings",
            "POST",
            {"device_id": "PIXEL-03", "sim_slot": 1},
            user_token=issued["key"],
        )
        with self.assertRaises(HTTPError) as raised:
            self.request(
                "/api/v1/bindings",
                "POST",
                {"device_id": "PIXEL-04", "sim_slot": 1},
                user_token=issued["key"],
            )
        self.assertEqual(raised.exception.code, 409)

    def test_bundled_skill_client_reads_key_scoped_status(self):
        _, issued = self.request(
            "/api/v1/admin/keys",
            "POST",
            {
                "phone_number": "+8613600000004",
                "device_id": "SEA-AL10-01",
                "sim_slot": 1,
            },
            admin=True,
        )
        script = (
            Path(__file__).resolve().parents[1]
            / "skills"
            / "vibesms"
            / "scripts"
            / "vibesms.py"
        )
        environment = {
            **os.environ,
            "VIBESMS_KEY": issued["key"],
            "VIBESMS_BASE_URL": self.base_url,
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        completed = subprocess.run(
            [sys.executable, str(script), "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            env=environment,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["phone_number"], "+8613600000004")
        self.assertEqual(payload["sim_slot"], 1)

    def test_skill_distribution_metadata_is_descriptive(self):
        root = Path(__file__).resolve().parents[1]
        metadata = json.loads(
            (root / "skills.sh.json").read_text(encoding="utf-8")
        )
        grouping = metadata["groupings"][0]

        self.assertEqual(grouping["skills"], ["vibesms"])
        self.assertIn("Android phone number", grouping["description"])

        skill = (root / "skills" / "vibesms" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("supports four focused actions", skill)

    def test_disabled_key_cannot_be_rotated_over_active_replacement(self):
        _, old_key = self.request(
            "/api/v1/admin/keys",
            "POST",
            {"phone_number": "+8613500000005"},
            admin=True,
        )
        self.request(
            "/api/v1/admin/keys/%s/disable" % old_key["key_id"],
            "POST",
            {},
            admin=True,
        )
        self.request(
            "/api/v1/admin/keys",
            "POST",
            {"phone_number": "+8613500000005"},
            admin=True,
        )
        with self.assertRaises(HTTPError) as raised:
            self.request(
                "/api/v1/admin/keys/%s/rotate" % old_key["key_id"],
                "POST",
                {},
                admin=True,
            )
        self.assertEqual(raised.exception.code, 409)


if __name__ == "__main__":
    unittest.main()
