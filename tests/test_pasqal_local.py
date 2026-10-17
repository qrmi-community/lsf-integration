import importlib.util
import json
import os
from pathlib import Path
import pwd
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


QRMI = types.SimpleNamespace(
    QuantumResource=Mock(),
    ResourceType=types.SimpleNamespace(PasqalLocal="pasqal-local"),
    ResourceStatusCode=types.SimpleNamespace(Online="online"),
)
SPEC = importlib.util.spec_from_file_location(
    "lsf_pasqal_local", Path(__file__).resolve().parents[1] / "pasqal_local.py"
)
hooks = importlib.util.module_from_spec(SPEC)
with patch.dict(sys.modules, {"qrmi": QRMI}):
    SPEC.loader.exec_module(hooks)


class PasqalLocalHooksTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.directory = root / "1234.7"
        self.config = root / "qrmi_config.json"
        self.config.write_text(json.dumps({"resources": [
            {"name": name, "type": "pasqal-local",
             "environment": {"QRMI_WARDEN_URL": "http://warden:4207"}}
            for name in ("local_a", "local_b")
        ]}))
        for patcher in (
            patch.object(hooks, "STATE_ROOT", root),
            patch.object(hooks, "CONFIG_PATH", self.config),
            patch.dict(os.environ, {
                "LSB_JOBID": "1234", "LSB_JOBINDEX": "7",
                "LSB_JOB_EXECUSER": pwd.getpwuid(os.getuid()).pw_name,
                "QRMI_QPU_RESOURCES": "local_a,local_b",
                "QRMI_WARDEN_URL": "http://untrusted.invalid",
                "QRMI_JOB_UID": "9999", "QRMI_JOB_ID": "forged",
            }),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        QRMI.QuantumResource.reset_mock(side_effect=True, return_value=True)
        self.resources = {name: Mock() for name in ("local_a", "local_b")}
        for name, resource in self.resources.items():
            resource.status.return_value.status = "online"
            resource.acquire.return_value = f"token-{name}"
        QRMI.QuantumResource.from_config.side_effect = lambda name, *_: self.resources[name]

    def test_identity_and_admin_configuration(self):
        """Use scheduler identity and administrator endpoints despite user overrides."""
        hooks.acquire_sessions()
        for call in QRMI.QuantumResource.from_config.call_args_list:
            config = call.args[2]
            self.assertEqual(config["QRMI_JOB_UID"], str(os.getuid()))
            self.assertEqual(config["QRMI_JOB_ID"], "1234[7]")
            self.assertEqual(config["QRMI_WARDEN_URL"], "http://warden:4207")
        self.assertEqual((self.directory / "sessions.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.directory / "environment.json").stat().st_mode & 0o777, 0o400)
        self.assertEqual(hooks.load_session("local_a")["token"], "token-local_a")
        hooks.release_sessions()
        self.assertFalse(self.directory.exists())

    def test_cleanup_ignores_user_handoff(self):
        """Release original sessions even when the user changes their readable handoff."""
        hooks.acquire_sessions()
        public = self.directory / "environment.json"
        public.chmod(0o600)
        public.write_text(json.dumps({"local_a": {"token": "forged"}}))
        hooks.release_sessions()
        self.resources["local_a"].release.assert_called_once_with("token-local_a")
        self.resources["local_b"].release.assert_called_once_with("token-local_b")

    def test_partial_acquisition_failure(self):
        """Release earlier sessions when a later acquisition fails."""
        self.resources["local_b"].acquire.side_effect = RuntimeError("acquire failed")
        with self.assertRaisesRegex(RuntimeError, "acquire failed"):
            hooks.acquire_sessions()
        self.resources["local_a"].release.assert_called_once_with("token-local_a")
        self.assertFalse(self.directory.exists())

    def test_release_failure_retains_only_failed_sessions(self):
        """Continue cleanup after a failure and preserve the failed token for retry."""
        hooks.acquire_sessions()
        self.resources["local_a"].release.side_effect = RuntimeError("release failed")
        with self.assertRaisesRegex(RuntimeError, "cleanup is incomplete"):
            hooks.release_sessions()
        self.resources["local_b"].release.assert_called_once_with("token-local_b")
        records = json.loads((self.directory / "sessions.json").read_text())
        self.assertEqual(list(records), ["local_a"])
        self.resources["local_a"].release.side_effect = None
        hooks.release_sessions()
        self.assertFalse(self.directory.exists())

    def test_retry_releases_previous_attempt(self):
        """Clean up a prior attempt before reacquiring sessions for the same LSF job."""
        hooks.acquire_sessions()
        (self.directory / "sessions.tmp").write_text("interrupted write")
        hooks.acquire_sessions()
        self.resources["local_a"].release.assert_called_once_with("token-local_a")
        self.assertEqual(self.resources["local_a"].acquire.call_count, 2)
        hooks.release_sessions()

    def test_offline_resources_have_no_sessions(self):
        """Publish an empty handoff when no requested Local resource is online."""
        for resource in self.resources.values():
            resource.status.return_value.status = "offline"
        hooks.acquire_sessions()
        self.assertIsNone(hooks.load_session("local_a"))
        hooks.release_sessions()
        self.assertFalse(self.directory.exists())

    def test_classical_jobs_do_not_need_sessions(self):
        """Leave classical jobs alone and allow post-exec without a pre-exec record."""
        self.config.unlink()
        with patch.dict(os.environ, {"QRMI_QPU_RESOURCES": ""}):
            hooks.acquire_sessions()
        hooks.release_sessions()
        QRMI.QuantumResource.from_config.assert_not_called()

    def test_hooks_require_root(self):
        """Reject direct hook invocation by a job user."""
        with patch.object(os, "geteuid", return_value=1002):
            with self.assertRaises(PermissionError):
                hooks.main()

    def test_job_id_cannot_escape_state_directory(self):
        """Reject path fragments in scheduler job IDs."""
        with patch.dict(os.environ, {"LSB_JOBID": "../../elsewhere"}):
            with self.assertRaises(ValueError):
                hooks.session_directory()


if __name__ == "__main__":
    unittest.main()
