"""Run a Pulser JSON sequence on a Pasqal resource allocated by LSF."""

import argparse
import time
from pathlib import Path

from qrmi import Payload, QRMIService, ResourceType, TaskStatus


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("sequence", type=Path, help="Pulser abstract representation JSON")
parser.add_argument("--runs", type=int, default=100, help="Number of samples")
args = parser.parse_args()

resources = [
    resource for resource in QRMIService().resources()
    if resource.resource_type() in (ResourceType.PasqalCloud, ResourceType.PasqalLocal)
]
if len(resources) != 1:
    raise ValueError("Request exactly one Pasqal resource through QRMI_QPU_RESOURCES.")

qrmi = resources[0]
print(f"Selected resource: {qrmi.resource_id()}", flush=True)
# The LSF hooks own acquisition and release; reuse their session in this process.
task_id = qrmi.task_start(
    Payload.PasqalCloud(sequence=args.sequence.read_text(), job_runs=args.runs)
)
print(f"Task ID: {task_id}", flush=True)
while (status := qrmi.task_status(task_id)) not in (
    TaskStatus.Completed, TaskStatus.Failed, TaskStatus.Cancelled,
):
    time.sleep(1)
print(f"Task ended - {status}", flush=True)
if status != TaskStatus.Completed:
    raise RuntimeError(qrmi.task_logs(task_id))
print(qrmi.task_result(task_id).value)
