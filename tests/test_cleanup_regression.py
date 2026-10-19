import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

JOBSTARTER = Path(__file__).resolve().parents[1] / "jobstarter.qrmi"


class CleanupRegressionTests(unittest.TestCase):
    def run_scenario(self, scenario, app_exit=0, resource_types=None, environment=None,
                     app_code=None, config_environment=None, pasqal_example=False,
                     private_environment=None):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            config = {
                "resources": [
                    {
                        "name": name,
                        "type": resource_type,
                        "environment": config_environment or {},
                    }
                    for name, resource_type in zip(
                        ("resource_a", "resource_b"),
                        resource_types or ("qiskit-runtime-service",) * 2,
                    )
                ]
            }
            (tmp / "qrmi_config.json").write_text(json.dumps(config))
            if private_environment:
                (tmp / ".config").mkdir()
                (tmp / ".config/qrmi_config.json").write_text(json.dumps({"resources": [
                    {"name": "resource_a", "environment": private_environment}]}))

            mock_module = tmp / "qrmi.py"
            mock_module.write_text("""
import json
import os

class ResourceType:
    IBMQuantumSystem = 1
    IBMQuantumComputeService = 2
    IBMQiskitRuntimeService = 3
    PasqalCloud = 4
    PasqalLocal = 5
    AliceBobFelis = 6
    IQMServer = 7
    OQTOPUS = 8

class ResourceStatusCode:
    Online = "online"

class ResourceProvider:
    pass

class TaskStatus:
    Completed = "completed"
    Failed = "failed"
    Cancelled = "cancelled"

class Payload:
    @staticmethod
    def PasqalCloud(sequence, job_runs):
        return {"sequence": sequence, "job_runs": job_runs}

class QRMIService:
    def resources(self):
        return [
            QuantumResource(name, resource_type)
            for name, resource_type in zip(
                os.environ["QRMI_JOB_QPU_RESOURCES"].split(","),
                os.environ["QRMI_JOB_QPU_TYPES"].split(","),
            )
        ]

class Status:
    def __init__(self, status):
        self.status = status

    def to_dict(self):
        return {"status": self.status}

class QuantumResource:
    def __init__(self, name, resource_type=None):
        self.name = name
        self.type = resource_type

    @classmethod
    def from_config(cls, name, resource_type, config):
        with open(os.path.join(os.environ["LSF_ENVDIR"], name + ".json"), "w") as f:
            json.dump(config, f)
        return cls(name)

    def resource_id(self):
        return self.name

    def resource_type(self):
        if self.type == "pasqal-cloud":
            return ResourceType.PasqalCloud
        if self.type == "pasqal-local":
            return ResourceType.PasqalLocal
        return "mock"

    def task_start(self, payload):
        assert os.environ[f"{self.name}_QRMI_JOB_ACQUISITION_TOKEN"] == f"token-{self.name}"
        assert payload == {"sequence": "{}", "job_runs": 10}
        with open(os.environ["EVENT_LOG"], "a") as f:
            f.write(f"task:{self.name}\\n")
        return "task-1"

    def task_status(self, task_id):
        return {"task_failure": TaskStatus.Failed,
                "task_cancelled": TaskStatus.Cancelled}.get(
                    os.getenv("SCENARIO"), TaskStatus.Completed)

    def task_result(self, task_id):
        from types import SimpleNamespace
        return SimpleNamespace(value='{"counter": {"0000": 10}}')

    def task_logs(self, task_id):
        return "Mock task did not complete"

    def status(self):
        scenario = os.getenv("SCENARIO")
        if scenario == "offline_all":
            return Status("offline")
        if scenario == "offline_first" and self.name == "resource_a":
            return Status("offline")
        if scenario == "offline_second" and self.name == "resource_b":
            return Status("offline")
        return Status(ResourceStatusCode.Online)

    def acquire(self):
        if (os.getenv("SCENARIO") == "acquire_failure"
                and self.name == "resource_b"):
            raise RuntimeError("Simulated acquisition failure")
        with open(os.environ["EVENT_LOG"], "a") as f:
            f.write(f"acquire:{self.name}\\n")
        if (os.getenv("SCENARIO") == "missing_token"
                and self.name == "resource_a"):
            return ""
        return f"token-{self.name}"

    def release(self, token):
        with open(os.environ["EVENT_LOG"], "a") as f:
            f.write(f"release:{self.name}\\n")
        if (os.getenv("SCENARIO") == "release_failure"
                and self.name == "resource_a"):
            raise RuntimeError("Simulated release failure")
""")

            event_log = tmp / "events.log"
            env = os.environ.copy()
            env.update({
                "PYTHONPATH": str(tmp),
                "HOME": str(tmp),
                "LSF_ENVDIR": str(tmp),
                "QRMI_QPU_RESOURCES": "resource_a,resource_b",
                "LSF_QRMI_DEBUG": "1",
                "SCENARIO": scenario,
                "EVENT_LOG": str(event_log),
            })
            env.update(environment or {})
            (tmp / "sitecustomize.py").write_text(
                f"import sys\nsys.path.insert(0, {str(JOBSTARTER.parent)!r})\n"
                f"import pasqal_local\nfrom pathlib import Path\n"
                f"pasqal_local.STATE_ROOT = Path({str(tmp / 'state')!r})\n"
            )
            local_records = {}
            for resource in config["resources"]:
                if resource["type"] != "pasqal-local":
                    continue
                index = env.get("LSB_JOBINDEX", "0")
                job_id = env["LSB_JOBID"]
                local_config = {**resource["environment"], "QRMI_JOB_UID": str(os.getuid()),
                                "QRMI_JOB_ID": f"{job_id}[{index}]" if index != "0" else job_id}
                name = resource["name"]
                local_records[name] = {"config": local_config, "token": f"token-{name}"}
                (tmp / f"{name}.json").write_text(json.dumps(local_config))
            if local_records and scenario != "missing_pre_hook":
                directory = tmp / "state" / f"{env['LSB_JOBID']}.{env.get('LSB_JOBINDEX', '0')}"
                directory.mkdir(parents=True)
                (directory / "environment.json").write_text(json.dumps(local_records))
            app_args = (
                [sys.executable, "-c", app_code] if app_code is not None
                else ["/bin/sh", "-c", f"exit {app_exit}"]
            )
            if pasqal_example:
                sequence = tmp / "sequence.json"
                sequence.write_text("{}")
                app_args = [sys.executable, str(JOBSTARTER.parent / "examples/pasqal.py"),
                            str(sequence), "--runs", "10"]

            result = subprocess.run(
                [
                    sys.executable,
                    str(JOBSTARTER),
                    *app_args,
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )

            events = (
                event_log.read_text().splitlines()
                if event_log.exists()
                else []
            )

            return result, events

    def test_offline_second_resource(self):
        result, events = self.run_scenario("offline_second")

        print("\\nOffline second resource:", result.returncode, events)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(events, [
            "acquire:resource_a",
            "release:resource_a",
        ])

    def test_offline_first_resource(self):
        result, events = self.run_scenario("offline_first")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(events, [
            "acquire:resource_b",
            "release:resource_b",
        ])

    def test_all_resources_offline(self):
        result, events = self.run_scenario("offline_all")

        self.assertEqual(result.returncode, 99)
        self.assertEqual(events, [])
        self.assertIn("No specified quantum resources", result.stderr)

    def test_first_release_failure(self):
        result, events = self.run_scenario("release_failure")

        print("\\nFirst release failure:", result.returncode, events)

        self.assertIn("release:resource_a", events)

        # Expected safe behavior; likely fails on current upstream.
        self.assertIn("release:resource_b", events)



    def test_success_releases_all_resources(self):
        result, events = self.run_scenario("normal")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(events, [
            "acquire:resource_a",
            "acquire:resource_b",
            "release:resource_a",
            "release:resource_b",
        ])

    def test_exit_42_releases_all_resources(self):
        result, events = self.run_scenario("normal", app_exit=42)
        self.assertEqual(result.returncode, 42)
        self.assertIn("release:resource_a", events)
        self.assertIn("release:resource_b", events)

    def test_exit_255_releases_all_resources(self):
        result, events = self.run_scenario("normal", app_exit=255)
        self.assertEqual(result.returncode, 255)
        self.assertIn("release:resource_a", events)
        self.assertIn("release:resource_b", events)

    def test_release_failure_preserves_application_status(self):
        result, events = self.run_scenario(
            "release_failure", app_exit=42
        )
        self.assertEqual(result.returncode, 42)
        self.assertIn("release:resource_a", events)
        self.assertIn("release:resource_b", events)


    def test_second_acquisition_failure_releases_first(self):
        result, events = self.run_scenario("acquire_failure")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("acquire:resource_a", events)
        self.assertIn("release:resource_a", events)

    def test_missing_first_token_still_releases_second(self):
        result, events = self.run_scenario("missing_token")
        self.assertIn("acquire:resource_a", events)
        self.assertIn("acquire:resource_b", events)
        self.assertIn("release:resource_b", events)
        self.assertIn("Missing token for resource_a", result.stderr)

    def test_pasqal_local_job_identity(self):
        """Pass LSF identity to acquisition and the application, including array indices."""
        for index, job_id in (("0", "1234"), ("7", "1234[7]")):
            with self.subTest(index=index):
                result, events = self.run_scenario(
                    "normal", resource_types=("pasqal-local",),
                    environment={"LSB_JOBID": "1234", "LSB_JOBINDEX": index,
                                 "QRMI_JOB_ID": "stale", "QRMI_JOB_UID": "9999"},
                    config_environment={"QRMI_WARDEN_URL": "http://warden:4207"},
                    app_code="""
import json, os
from pathlib import Path
config = json.loads((Path(os.environ["LSF_ENVDIR"]) / "resource_a.json").read_text())
for key in ("QRMI_JOB_ID", "QRMI_JOB_UID"):
    assert config[key] == os.environ[key]
assert os.environ["resource_a_QRMI_WARDEN_URL"] == config["QRMI_WARDEN_URL"]
assert os.environ["resource_a_QRMI_JOB_ACQUISITION_TOKEN"] == "token-resource_a"
assert os.environ["QRMI_JOB_QPU_TYPES"] == "pasqal-local"
print(json.dumps(config))
""",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                config = json.loads(result.stdout)
                self.assertEqual(config["QRMI_JOB_UID"], str(os.getuid()))
                self.assertEqual(config["QRMI_JOB_ID"], job_id)
                self.assertEqual(events, [])

    def test_pasqal_cloud_credentials(self):
        """Forward Cloud credentials and config paths without logging their values."""
        environment = {
            "HOME": "/home/lsfuser",
            "PASQAL_CONFIG_ROOT": "/private/pasqal",
            "PASQAL_USERNAME": "private-user",
            "PASQAL_PASSWORD": "private-password",
            "QRMI_PASQAL_CLOUD_AUTH_TOKEN": "private-token",
            "QRMI_PASQAL_CLOUD_PROJECT_ID": "user-project",
        }
        result, events = self.run_scenario(
            "normal", resource_types=("pasqal-cloud",), environment=environment,
            config_environment={"QRMI_PASQAL_CLOUD_PROJECT_ID": "site-project"},
            app_code="""
import json, os
from pathlib import Path
config = json.loads((Path(os.environ["LSF_ENVDIR"]) / "resource_a.json").read_text())
assert os.environ["resource_a_QRMI_PASQAL_CLOUD_PROJECT_ID"] == "user-project"
assert os.environ["resource_a_QRMI_PASQAL_CLOUD_AUTH_TOKEN"] == "private-token"
print(json.dumps(config))
""",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        for key, value in environment.items():
            self.assertEqual(config[key], value)
        for value in ("private-user", "private-password", "private-token", "token-resource_a"):
            self.assertNotIn(value, result.stderr)
        self.assertEqual(events, ["acquire:resource_a", "release:resource_a"])

    def test_private_config_precedence(self):
        """Override site configuration with the user's file, and that with the environment."""
        result, events = self.run_scenario(
            "normal", resource_types=("pasqal-cloud",),
            config_environment={"QRMI_PASQAL_CLOUD_PROJECT_ID": "site-project",
                                "QRMI_PASQAL_CLOUD_AUTH_ENDPOINT": "site-endpoint"},
            private_environment={"QRMI_PASQAL_CLOUD_PROJECT_ID": "user-project",
                                 "QRMI_PASQAL_CLOUD_AUTH_ENDPOINT": "user-endpoint"},
            environment={"QRMI_PASQAL_CLOUD_AUTH_ENDPOINT": "env-endpoint"},
            app_code="""
import os
assert os.environ["resource_a_QRMI_PASQAL_CLOUD_PROJECT_ID"] == "user-project"
assert os.environ["resource_a_QRMI_PASQAL_CLOUD_AUTH_ENDPOINT"] == "env-endpoint"
""",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(events, ["acquire:resource_a", "release:resource_a"])

    def test_classical_job(self):
        """Run a job without quantum resources and propagate its exit status."""
        result, events = self.run_scenario("normal", app_exit=3,
                                           environment={"QRMI_QPU_RESOURCES": ""})
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(events, [])

    def test_mixed_ibm_pasqal_cleanup(self):
        """Release IBM and Pasqal resources after an application failure."""
        result, events = self.run_scenario(
            "normal", app_exit=42,
            resource_types=("qiskit-runtime-service", "pasqal-local"),
            environment={"LSB_JOBID": "1234"},
        )
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertEqual(events, ["acquire:resource_a", "release:resource_a"])

    def test_pasqal_example_reuses_session(self):
        """Run the same example on both Pasqal types without acquiring a second session."""
        for resource_type in ("pasqal-cloud", "pasqal-local"):
            with self.subTest(resource_type=resource_type):
                result, events = self.run_scenario(
                    "normal", resource_types=(resource_type,), pasqal_example=True,
                    environment={"LSB_JOBID": "1234"},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('"counter": {"0000": 10}', result.stdout)
                expected = (["acquire:resource_a", "task:resource_a", "release:resource_a"]
                            if resource_type == "pasqal-cloud" else ["task:resource_a"])
                self.assertEqual(events, expected)

    def test_pasqal_local_requires_pre_hook(self):
        """Reject a Local job without a prepared session instead of acquiring as the user."""
        result, events = self.run_scenario(
            "missing_pre_hook", resource_types=("pasqal-local",),
            environment={"LSB_JOBID": "1234",
                         "resource_a_QRMI_JOB_ACQUISITION_TOKEN": "user-supplied-token"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires the privileged LSF pre-execution hook", result.stderr)
        self.assertEqual(events, [])

    def test_pasqal_example_failure_status(self):
        """Report failed and cancelled tasks as application failures and release the resource."""
        for scenario in ("task_failure", "task_cancelled"):
            with self.subTest(scenario=scenario):
                result, events = self.run_scenario(
                    scenario, resource_types=("pasqal-cloud",), pasqal_example=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Mock task did not complete", result.stderr)
                self.assertEqual(events, ["acquire:resource_a", "task:resource_a",
                                          "release:resource_a"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
