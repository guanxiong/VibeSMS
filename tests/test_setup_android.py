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
        self.assertEqual(SETUP_ANDROID.RELEASE_VERSION, "0.2.0")
        self.assertTrue(SETUP_ANDROID.RELEASE_BASE.startswith("https://github.com/"))
        self.assertEqual(SETUP_ANDROID.APK_NAME, "VibeSMS-0.2.0.apk")

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


if __name__ == "__main__":
    unittest.main()
