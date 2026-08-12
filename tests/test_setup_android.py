import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_DIRECTORY = Path(__file__).resolve().parents[1] / "skills" / "vibesms" / "scripts"
sys.path.insert(0, str(SCRIPT_DIRECTORY))
SPEC = importlib.util.spec_from_file_location(
    "vibesms_setup_android", SCRIPT_DIRECTORY / "setup_android.py"
)
SETUP_ANDROID = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SETUP_ANDROID)


class AndroidSetupScriptTest(unittest.TestCase):
    def test_release_asset_is_versioned_and_https(self):
        self.assertEqual(SETUP_ANDROID.RELEASE_VERSION, "0.4.9")
        self.assertTrue(SETUP_ANDROID.RELEASE_BASE.startswith("https://github.com/"))
        self.assertEqual(SETUP_ANDROID.APK_NAME, "VibeSMS-0.4.9.apk")

    def test_provision_receiver_success_is_accepted(self):
        SETUP_ANDROID.verify_provision_result(
            'Broadcasting: Intent {...}\nBroadcast completed: result=0, data="VibeSMS terminal provisioned"\n'
        )

    def test_provision_receiver_failure_keeps_safe_detail(self):
        with self.assertRaisesRegex(RuntimeError, "selected SIM is not active"):
            SETUP_ANDROID.verify_provision_result(
                'Broadcast completed: result=3, data="selected SIM is not active"\n'
            )

    def test_missing_receiver_result_is_not_treated_as_success(self):
        with self.assertRaisesRegex(RuntimeError, "no receiver result"):
            SETUP_ANDROID.verify_provision_result("Broadcasting: Intent {...}\n")

    def test_android_keepalive_is_doze_aware_and_bounded(self):
        root = Path(__file__).resolve().parents[1]
        receiver = (
            root
            / "android"
            / "app"
            / "src"
            / "main"
            / "java"
            / "ai"
            / "shareapi"
            / "vibesms"
            / "KeepAliveReceiver.java"
        ).read_text(encoding="utf-8")
        manifest = (
            root / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
        ).read_text(encoding="utf-8")
        setup_script = (SCRIPT_DIRECTORY / "setup_android.py").read_text(encoding="utf-8")
        service = (
            root
            / "android"
            / "app"
            / "src"
            / "main"
            / "java"
            / "ai"
            / "shareapi"
            / "vibesms"
            / "KeepAliveService.java"
        ).read_text(encoding="utf-8")
        self.assertIn("setExactAndAllowWhileIdle", receiver)
        self.assertIn("setAndAllowWhileIdle", receiver)
        self.assertIn("WAKE_LOCK_TIMEOUT_MS", receiver)
        self.assertIn("UploadScheduler.enqueueHeartbeat", receiver)
        self.assertIn("android.permission.WAKE_LOCK", manifest)
        self.assertIn("android.permission.FOREGROUND_SERVICE", manifest)
        self.assertIn("START_STICKY", service)
        self.assertIn("startForeground", service)
        activity = (
            root
            / "android"
            / "app"
            / "src"
            / "main"
            / "java"
            / "ai"
            / "shareapi"
            / "vibesms"
            / "MainActivity.java"
        ).read_text(encoding="utf-8")
        terminal_config = (
            root
            / "android"
            / "app"
            / "src"
            / "main"
            / "java"
            / "ai"
            / "shareapi"
            / "vibesms"
            / "TerminalConfig.java"
        ).read_text(encoding="utf-8")
        self.assertIn("statusHandler.postDelayed", activity)
        self.assertIn("isIgnoringBatteryOptimizations", activity)
        self.assertIn("openHuaweiAppLaunchSettings", activity)
        self.assertIn("openHuaweiBatterySettings", activity)
        self.assertIn("lastSuccessfulUploadAt", activity)
        self.assertIn("huawei_app_launch_confirmed", terminal_config)
        self.assertIn("huawei_sleep_network_confirmed", terminal_config)
        self.assertIn("ZoneId.systemDefault()", terminal_config)
        self.assertIn("parseLegacyTime", terminal_config)
        self.assertIn("deviceidle", setup_script)


if __name__ == "__main__":
    unittest.main()
