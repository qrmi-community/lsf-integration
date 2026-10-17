#!/opt/lsfce/pyenv/bin/python3 -I
"""Manage Warden sessions in LSF's privileged queue pre/post hooks."""

import json
import os
from pathlib import Path
import pwd
import sys

from qrmi import QuantumResource, ResourceStatusCode, ResourceType

CONFIG_PATH = Path("/opt/lsfce/conf/qrmi_config.json")
STATE_ROOT = Path("/run/lsf-qrmi")


def session_directory():
    """Return the state directory for this LSF job or array element.

    Returns:
        (Path): Directory under the root-owned state directory.
    """
    job_id = int(os.environ["LSB_JOBID"])
    index = int(os.getenv("LSB_JOBINDEX", "0"))
    return STATE_ROOT / f"{job_id}.{index}"


def load_session(name):
    """Read the user-facing session prepared by the queue pre-execution hook.

    Args:
        name (str): Resource name in the scheduler configuration.

    Returns:
        (dict | None): Session record, or None when the resource was offline.
    """
    path = session_directory() / "environment.json"
    try:
        records = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise RuntimeError("Pasqal Local requires the privileged LSF pre-execution hook") from exc
    return records.get(name)


def save_records(path, records):
    """Write private cleanup state without exposing session tokens.

    Args:
        path (Path): File within a root-owned directory.
        records (dict): Acquired sessions keyed by resource name.
    """
    temporary = path.with_suffix(".tmp")
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as stream:
        json.dump(records, stream)
    temporary.replace(path)


def release_sessions():
    """Revoke sessions using private state, retaining failed releases for retry."""
    directory = session_directory()
    path = directory / "sessions.json"
    if not path.exists():
        return
    records = json.loads(path.read_text())
    failed = {}
    for name, record in records.items():
        try:
            resource = QuantumResource.from_config(name, ResourceType.PasqalLocal, record["config"])
            os.environ[f"{name}_QRMI_JOB_ACQUISITION_TOKEN"] = record["token"]
            resource.release(record["token"])
        except RuntimeError:
            print(f"Failed to release Pasqal Local resource {name}", file=sys.stderr)
            failed[name] = record
    (directory / "environment.json").unlink(missing_ok=True)
    if failed:
        save_records(path, failed)
        raise RuntimeError("Pasqal Local session cleanup is incomplete")
    path.unlink()
    (directory / "sessions.tmp").unlink(missing_ok=True)
    (directory / "environment.tmp").unlink(missing_ok=True)
    directory.rmdir()


def acquire_sessions():
    """Acquire requested Local resources as root for the LSF job's user."""
    resources = os.getenv("QRMI_QPU_RESOURCES")
    if not resources:
        return
    requested = {name.strip() for name in resources.split(",")}
    configs = json.loads(CONFIG_PATH.read_text())["resources"]
    local = {cfg["name"]: cfg for cfg in configs
             if cfg["type"] == "pasqal-local" and cfg["name"] in requested}
    if not local:
        return
    directory = session_directory()
    # A retry must clean up the previous attempt before opening another session.
    release_sessions()
    user = pwd.getpwnam(os.environ["LSB_JOB_EXECUSER"])
    job_id, index = directory.name.split(".")
    identity = {"QRMI_JOB_UID": str(user.pw_uid),
                "QRMI_JOB_ID": f"{job_id}[{index}]" if index != "0" else job_id}
    directory.mkdir(mode=0o711)
    directory.chmod(0o711)
    records = {}
    save_records(directory / "sessions.json", records)
    try:
        for name, cfg in local.items():
            config = {**cfg["environment"], **identity}
            resource = QuantumResource.from_config(name, ResourceType.PasqalLocal, config)
            if resource.status().status != ResourceStatusCode.Online:
                continue
            records[name] = {"config": config, "token": resource.acquire()}
            save_records(directory / "sessions.json", records)
        # The job can read its own handoff; post-exec only trusts sessions.json.
        public = directory / "environment.json"
        save_records(public, records)
        public.chmod(0o400)
        os.chown(public, user.pw_uid, user.pw_gid)
    except BaseException:
        release_sessions()
        raise


def main():
    """Run a fixed queue-level hook under the scheduler's root identity."""
    if os.geteuid() != 0:
        raise PermissionError("Pasqal Local pre/post hooks must run as root")
    if sys.argv[1] == "acquire":
        acquire_sessions()
    elif sys.argv[1] == "release":
        release_sessions()
    else:
        raise ValueError("Expected acquire or release")


if __name__ == "__main__":
    main()
