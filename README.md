# lsf-integration

The "original" LSF-QRMI project is located at https://github.ibm.com/QCHPC/lsf-qpu/ and now https://github.ibm.com/IBM/lsf-qrmi. This repository uses LSF Community Edition in a management/login node (lsf-head) and two compute nodes (compute01 and compute02). The jobstarter hook (jobstarter.qrmi) acquires resources, launches the application, and releases resources in a `finally` block. Pasqal Local sessions are acquired and released by separate privileged queue pre/post hooks, so their cleanup also runs when LSF kills the jobstarter. Other resource cleanup cannot run if the jobstarter itself is killed with SIGKILL.

IBM submissions use QRMI_QPU_RESOURCES, QRMI_IBM_QRS_IAM_APIKEY, and optionally LSF_QRMI_DEBUG when running bsub (example below).

```
QRMI_QPU_RESOURCES=ibm_marrakesh QRMI_IBM_QRS_IAM_APIKEY=... LSF_QRMI_DEBUG=1 bsub -Is $HOME/examples/run_sampler.sh
```

The administrator configures resources in `$LSF_ENVDIR/qrmi_config.json`
(`/opt/lsfce/conf/qrmi_config.json` in the containers). The jobstarter runs as the
job user, so this file must be readable by users. Keep credentials in the user's
environment or private credential file, not in this shared configuration.

## Instructions

```
# Download the matching archive as described in tutorial_downloads.md.
docker compose build --build-arg LSF_TAR=lsfsce10.2.0.15-x86_64.tar.Z
docker compose up -d
docker exec -it -u lsfuser -w /home/lsfuser lsf-head bash
# Simple interactive test
bsub -Is hostname
# Simple quantum test
QRMI_QPU_RESOURCES=ibm_marrakesh QRMI_IBM_QRS_IAM_APIKEY=... LSF_QRMI_DEBUG=1 bsub -Is $HOME/examples/run_sampler.sh
```

The initial configuration is copied into the shared LSF volume once. Rebuilding
the image alone does not replace files in these volumes. To upgrade an existing
cluster, finish running jobs first, rebuild, and recreate the containers with
the commands above. This starts MUNGE and installs `/etc/lsf.sudoers` and
`/run/lsf-qrmi` on every node. Then update the shared hooks and examples:

```bash
docker exec lsf-head bash -c '
    install -m 755 /distribution/jobstarter.qrmi /distribution/pasqal_local.py /opt/lsfce/conf/hooks/
    install -o lsfuser -g lsfuser -m 644 /distribution/examples/pasqal.py /home/lsfuser/examples/
    install -o lsfuser -g lsfuser -m 755 /distribution/examples/run_pasqal.sh /home/lsfuser/examples/
    chown root:root /opt/lsfce /opt/lsfce/conf /opt/lsfce/conf/qrmi_config.json
    chown -R root:root /opt/lsfce/conf/hooks /opt/lsfce/pyenv
'
```

Merge the Pasqal resource entries into `/opt/lsfce/conf/qrmi_config.json`, keeping
your existing site settings. Add the queue settings described below to `normal`
and `interactive` in `/opt/lsfce/conf/lsbatch/cluster1/configdir/lsb.queues` and
run `badmin reconfig` as the LSF administrator. Complete the MUNGE key and QRMI
wheel setup below before submitting Local jobs. Do not rerun `configure-lsf.sh`
on an existing installation: it is intended for initial setup.

## Pasqal Cloud

The supplied configuration includes `EMU_FREE`. The resource name is the Pasqal
Cloud backend name. Set the project and credentials in `~/.pasqal/config` as
`lsfuser` (the home directory is shared with both compute nodes):

```ini
project_id=<project UUID>
username=<Pasqal username>
password=<Pasqal password>
```

Restrict this file to its owner with `chmod 600 ~/.pasqal/config`. A `token=...`
entry can be used instead of username/password. The launcher also forwards
`PASQAL_USERNAME`, `PASQAL_PASSWORD`, and `PASQAL_CONFIG_ROOT`, or the following
QRMI environment variables:

```bash
export QRMI_PASQAL_CLOUD_PROJECT_ID="<project UUID>"
export QRMI_PASQAL_CLOUD_AUTH_TOKEN="<access token>"
```

To keep the file on the host instead, copy it into the cluster after
`docker compose up` (run on the host; replace `docker` with `podman` if needed):

```bash
docker exec lsf-head install -d -o lsfuser -g lsfuser -m 700 /home/lsfuser/.pasqal
docker cp ~/.pasqal/config lsf-head:/home/lsfuser/.pasqal/config
docker exec lsf-head chown lsfuser:lsfuser /home/lsfuser/.pasqal/config
docker exec lsf-head chmod 600 /home/lsfuser/.pasqal/config
```

`docker compose down -v` deletes this copy together with the home volume.

Export a Pulser sequence with `sequence.to_abstract_repr()` to
`$HOME/examples/sequence.json`. This file must be visible on the compute nodes.
The example reads this JSON directly through QRMI and needs no additional Python
packages.

Pulser is not installed in the containers. For example, this creates a
four-atom test sequence for EMU_FREE or Warden's emulator. Save it as
`make_sequence.py` in an environment with Pulser installed:

```python
from pathlib import Path
from pulser import Pulse, Register, Sequence
from pulser.devices import DigitalAnalogDevice

register = Register.square(2, spacing=8, prefix="q").with_automatic_layout(DigitalAnalogDevice)
sequence = Sequence(register, DigitalAnalogDevice)
sequence.declare_channel("rydberg", "rydberg_global")
sequence.add(Pulse.ConstantPulse(1000, 1, 0, 0), "rydberg")
sequence.measure("ground-rydberg")
Path("sequence.json").write_text(sequence.to_abstract_repr())
```

If you do not have such an environment, use a temporary one on `lsf-head`: as
`lsfuser`, save the script as `$HOME/examples/make_sequence.py` (`vim` is
available in the containers), then run it there. Pulser is about 100 MB to
download:

```bash
python3 -m venv /tmp/pulser && /tmp/pulser/bin/pip install pulser-core
cd $HOME/examples && /tmp/pulser/bin/python make_sequence.py
rm -rf /tmp/pulser
```

Use the actual target device and its layout when authoring for hardware. Copy
the JSON to `$HOME/examples/sequence.json` in the LSF cluster, then submit:

```bash
QRMI_QPU_RESOURCES=EMU_FREE bsub -Is \
    "$HOME/examples/run_pasqal.sh" "$HOME/examples/sequence.json" --runs 100
```

The example uses the resource published by the launcher, prints the task ID and
sample counts, and exits nonzero if the task fails or is cancelled. It does not
acquire a second session. `LSF_QRMI_DEBUG=1` logs environment variable names,
without printing credentials or acquisition tokens.

## Pasqal Local

The configuration includes `PASQAL_LOCAL` with `QRMI_WARDEN_URL=http://warden:4207`.
Replace this with the Warden URL reachable from the compute nodes. The pre-hook
maps LSF's `LSB_JOB_EXECUSER` to the Unix UID and `LSB_JOBID` to `QRMI_JOB_ID`, and
includes `LSB_JOBINDEX` for array jobs as `job_id[index]`. The jobstarter exports
this identity and the prepared session to the application.

Warden requires MUNGE authentication and administrator privileges to create and
revoke sessions. A stock QRMI wheel without the `munge` feature is insufficient;
both the hook and application need a MUNGE-enabled QRMI build. This setup was
tested with QRMI 0.26.3. From a QRMI source release, with Rust, Maturin and the
MUNGE development library installed, build:

```bash
maturin build --release --features pyo3,pyo3/abi3,munge
```

Use the resulting wheel in both environments. For an existing container cluster:

```bash
docker cp /path/to/qrmi-wheel.whl lsf-head:/shared/qrmi-wheel.whl
docker exec lsf-head /opt/lsfce/pyenv/bin/pip install --force-reinstall /shared/qrmi-wheel.whl
docker exec lsf-head /home/lsfuser/pyenv/bin/pip install --force-reinstall /shared/qrmi-wheel.whl
```

Replace `qrmi-wheel.whl` with the wheel's full filename. For a fresh installation,
the build argument `LSF_QRMI_PACKAGE` can specify a wheel URL or a wheel path visible
inside the container. The default is the PyPI `qrmi` package for Cloud/IBM use.

The containers run MUNGE with a key generated at first startup and shared through
the `munge_config` volume. Configure Warden's MUNGE daemon with the same key, or
copy the existing Warden MUNGE key into that volume as an administrator and
restart MUNGE on all LSF nodes. Keep the key owned by `munge`, mode `0400`. The
job user's numeric UID must agree on the LSF and Warden hosts. Warden must allow
UID `0` as an administrator for the hooks; job users remain ordinary Warden users.

The container setup installs these queue settings for `normal` and `interactive`:

```ini
PRE_EXEC = /opt/lsfce/conf/hooks/pasqal_local.py acquire
POST_EXEC = /opt/lsfce/conf/hooks/pasqal_local.py release
```

It also sets `LSB_PRE_POST_EXEC_USER=root` in `/etc/lsf.sudoers` on every LSF node.
This applies to queue-level hooks; the application and jobstarter still run as
the job user. See [IBM's pre/post execution configuration](https://www.ibm.com/docs/en/spectrum-lsf/10.1.0?topic=processing-configuration-modify-pre-post-execution).

The privileged hook uses only `/opt/lsfce/conf/qrmi_config.json` for endpoints,
ignoring user endpoint and identity overrides. Its script, configuration,
Python environment and parent directories must remain administrator-owned.
Python runs in isolated mode. Cleanup reads root-only session records under
`/run/lsf-qrmi/<job_id>.<index>/sessions.json`; the job reads a separate handoff
file. A failed release retains its private record for an administrator to retry
on the execution node with the same `LSB_JOBID` and `LSB_JOBINDEX`. For example,
to retry cleanup for array element `123[2]` on `compute01`:

```bash
docker exec -e LSB_JOBID=123 -e LSB_JOBINDEX=2 compute01 \
    /opt/lsfce/conf/hooks/pasqal_local.py release
```

Use index `0` for a non-array job. Warden session expiry handles node loss;
container recreation removes this node-local state.

Submit the same example as Cloud:

```bash
QRMI_QPU_RESOURCES=PASQAL_LOCAL bsub -Is \
    "$HOME/examples/run_pasqal.sh" "$HOME/examples/sequence.json" --runs 100
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

These tests stub QRMI and require no Cloud credentials or running LSF cluster.

## Links

[IBM LFS Community Edition (free after a simple registration process)](https://early-access.ibm.com/software/support/trial/cst/programwebsite.wss?siteId=680&h=&tabId=&_gl=1*18pgo3p*_ga*ODgwNjAzMzMzLjE3OTEyOTM1ODI.*_ga_FYECCCS21D*czE3OTEyOTM1ODEkbzEkZzEkdDE3OTEyOTM2NjUkajQ4JGwwJGgw)
