## Overview

This repository provides a vendor-neutral QRMI integration for IBM LSF Community Edition (CE). It demonstrates how QRMI can be used with LSF to schedule hybrid HPC-quantum workloads while supporting resource acquisition, scheduling retries, and quantum backend selection.

Key features include:

* Vendor-neutral QRMI integration
* Quantum backend selection
* Scheduling retries
* Containerized multi-host LSF environment
* Hybrid quantum-HPC workloads
* arm64 (aarch64) and x86_64 (amd64) support

## Prerequisites

* Podman/Podman Compose or Docker/Docker Compose
* IBM LSF CE download
  * arm64 (aarch64): lsfsce10.2.0.15-armv8.tar.Z
  * x86_64 (amd64): lsfsce10.2.0.15-x86_64.tar.Z
* IBM Quantum Platform account (for quantum examples)

## Quick Start Guide

First, an appropriate version of LSF Community Edition must be downloaded. This can be done [here](https://early-access.ibm.com/software/support/trial/cst/programwebsite.wss?siteId=680&h=&tabId=&_gl=1*18pgo3p*_ga*ODgwNjAzMzMzLjE3OTEyOTM1ODI.*_ga_FYECCCS21D*czE3OTEyOTM1ODEkbzEkZzEkdDE3OTEyOTM2NjUkajQ4JGwwJGgw) after registering with IBM or by following the directions in `tutorial_downloads.md` if you are participating in the SC26 tutorial.

Once the `lsf-integration` directory has either `lsfsce10.2.0.15-armv8.tar.Z` or `lsfsce10.2.0.15-x86_64.tar.Z`, `podman compose` can be used to create and start the containers as shown below.

```bash
podman compose build --build-arg LSF_TAR=lsfsce10.2.0.15-armv8.tar.Z
podman compose up
```

The diagram below shows the container environment. `lsf-head` is a management/login host. `compute01` and `compute02` are execution hosts.

<p align="center">
<img src="figures/lsf-cluster.png" width="700">
</p>

After the containers are running, log into `lsf-head` as `lsfuser` as shown below, check the LSF installation with `bhosts`, and run a simple job. `lsf-head` is closed because it is configured not to accept jobs.

```bash
podman exec -it -u lsfuser -w /home/lsfuser lsf-head bash
bhosts
```

The output from `bhosts` should match the following.

```
HOST_NAME          STATUS       JL/U    MAX  NJOBS    RUN  SSUSP  USUSP    RSV
compute01.dns.podm ok              -      8      0      0      0      0      0
compute02.dns.podm ok              -      8      0      0      0      0      0
lsf-head           closed          -      0      0      0      0      0      0
```

To run a simple job, use the following.

```bash
bsub -Is hostname
```

The output from `bsub` should be similar to the following. LSF could decide to run `hostname` on `compute01` instead of `compute02`.

```
Job <1> is submitted to default queue <interactive>.
<<Waiting for dispatch ...>>
<<Starting on compute02>>
compute02
```

A simple quantum application (sampler) can be found in the examples directory. It can be run as shown below. The default delimiter `QRMI_QPU_RESOURCES` is ',' and it can be changed through `QRMI_DELIMITER`. Debug messages are enabled with `LSF_QRMI_DEBUG=1` and disabled with `LSF_QRMI_DEBUG=0` or if `LSF_QRMI_DEBUG` is not defined.

```bash
QRMI_QPU_RESOURCES=ibm_marrakesh QRMI_IBM_QRS_IAM_APIKEY=... LSF_QRMI_DEBUG=1 bsub -Is $HOME/examples/run_sampler.sh
```

The example above shows one method to pass the API key through the `QRMI_IBM_QRS_IAM_APIKEY` environment variable. An alternate method is to place API keys in `$HOME/.config/qrmi_config.json`. `$LSF_ENVDIR/qrmi_config.json` contains public information but not private information because it must be readable by all users. `$HOME/.config/qrmi_config.json` contains private information such as API keys. The evaluation order is `$LSF_ENVDIR/qrmi_config.json` then `$HOME/.config/qrmi_config.json` and finally environment variables. In other words, environment variables set by the user override values in both `$LSF_ENVDIR/qrmi_config.json` and `$HOME/.config/qrmi_config.json`.

A bsub script can also be used as shown below. This example assumes `QRMI_IBM_QRS_IAM_APIKEY` has been defined for `ibm_marrakesh` in `$HOME/.config/qrmi_config.json` because `QRMI_IBM_QRS_IAM_APIKEY` is not being defined as an environment variable by the user as in the example above.

```bash
bsub < $HOME/examples/run_sampler.bsub
```

MPI programs can be run using the installed MPICH. To run the MPI "Hello World" program in the `examples` directory, use the following steps:

```bash
( cd $HOME/examples; make )
bsub -Is -n 4 -R "span[ptile=2]" "mpirun $HOME/examples/mpi_hello_world"
```

Two MPI ranks should run on `compute01` and two on `compute02`.

### Basic LSF Commands

| Command   | Description |
|-----------|-------------|
| `lsadmin` | Administrator command to manage the base cluster infrastructure and host-level daemons (lim and res). |
| `badmin`  | Administrator command to manage the batch scheduling engine and job-level daemons (mbatchd and sbatchd) |
| `bhosts`  | Displays the status and resource availability of execution hosts in the cluster |
| `bsub`    | Submits a new job to the LSF batch system |
| `bjobs`   | Displays information about active, pending, and recently completed jobs |
| `bkill`   | Sends a signal to terminate or cancel running or pending jobs |
| `bacct`   | Displays historical accounting statistics for completed jobs |

### Installation and Configuration Scripts

`docker-entrypoint.sh` orchestrates the bring up of the containers which share `/opt` (LSF and MPICH), `/home`, and `/shared`. `/shared` is bind-mounted from `./shared` next to `docker-compose.yml`, which Compose creates on first start.

`install-lsf.sh` installs LSF in `/opt/lsfce`. The script relies on `LSF_TAR` to determine which LSF download to use (`lsfsce10.2.0.15-armv8.tar.Z` or `lsfsce10.2.0.15-x86_64.tar.Z`).

`configure-lsf.sh` configures `lsf.conf`, `lsf.hosts`, `JOB_STARTER` hook, `qrmi_config.json`, and the QRMI runtime for `JOB_STARTER`. `lsf.conf` is configured to use `ssh` instead of `rsh`. `lsf.hosts` is configured to not allow jobs to run on `lsf-head`. `JOB_STARTER` hook is installed in `LSF_ENVDIR/hooks`. `qrmi_config.json` is installed in `LSF_ENVDIR`. `lsfadmin` is set as the owner of the LSF installation.

`configure-user.sh` installs the examples and the QRMI virtual environment for `lsfuser`. It modifies the `lsfadmin` and `lsfuser` `.bashrc` to source `LSF_ENVDIR/profile.lsf` to provide access to the LSF commands.

## LSF Quantum Job Flow

The diagram below shows the flow of an LSF quantum job to an IBM Quantum Platform (IQP) system (`ibm_marrakesh`). The user submits the job with bsub and specifies a list of quantum resources in `QRMI_QPU_RESOURCES` and an IQP API key in `QRMI_IBM_QRS_IAM_APIKEY`. The `mbatchd` on `lsf-head` decides where to run the job and dispatches the job to an `sbatchd` on `compute01` or `compute02`. `sbatchd` starts the job through the `JOB_STARTER` hook described in more detail below.

<p align="center">
<img src="figures/lsf-flow.png" width="1000">
</p>

The `JOB_STARTER` hook expects `QRMI_QPU_RESOURCES` to be defined for quantum jobs. Because the `qrmi_config.json` file only contains public information for the IQP open instance systems, the user must pass in a private API key to `bsub` through `QRMI_IBM_QRS_IAM_APIKEY`.

`JOB_STARTER` uses QRMI to obtain the status for each resource in `QRMI_QPU_RESOURCES`. If a resource is not available, it is skipped. If a resource is available, `JOB_STARTER` uses QRMI to obtain a token. If the token for a resource is not available, the resource is skipped. If the `JOB_STARTER` is able to acquire resources, it places acquired resources and types in the `QRMI_JOB_QPU_RESOURCES` and `QRMI_JOB_QPU_TYPES` environment variables and executes the job. After execution `JOB_STARTER` releases all the acquired resources.

If `JOB_STARTER` cannot acquire any available resources, it returns a special value to indicate to the scheduler to retry in the next scheduling cycle (every 5 seconds). The special value is defined by `REQUEUE_EXIT_VALUES`. The number of retries is defined by `MAX_JOB_REQUEUE`. Both are defined for the `normal` and `interactive` queues. After `MAX_JOB_REQUEUE` tries, the scheduler puts the job in `PSUSP` state. The job will remain in the queue in `PSUSP` state until the user removes it with `bkill <jobid>`.

One disadvantage of this design is that `compute01` or `compute02` is assigned to run a quantum job which is not necessary. Because `JOB_STARTER` is lightweight, an alternate design is to define a "quantum" queue that runs jobs on `lsf-head`.

## Pasqal Support

### Pasqal Cloud

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

### Pasqal Local

The configuration includes `PASQAL_LOCAL` with `QRMI_WARDEN_URL=http://warden:4207`.
Replace this with the Warden URL reachable from the compute nodes.

If Warden runs in a container on another container network, connect the LSF
containers to that network. List the networks of the Warden container (here
`warden`; use the name shown by `docker ps`):

```bash
docker inspect warden --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}'
```

Then connect the LSF containers to that network and check the connection:

```bash
for c in lsf-head compute01 compute02; do docker network connect <network> $c; done
docker exec compute01 curl -s http://warden:4207/accessible
```

With Podman, use `podman` instead of `docker`. The Warden container name then
resolves from the LSF nodes, so `QRMI_WARDEN_URL` can use it. Recreating the
containers (`docker compose down` and `up`) removes the connection; run the
loop again. The pre-hook
maps LSF's `LSB_JOB_EXECUSER` to the Unix UID and `LSB_JOBID` to `QRMI_JOB_ID`, and
includes `LSB_JOBINDEX` for array jobs as `job_id[index]`. The jobstarter exports
this identity and the prepared session to the application.

Warden requires MUNGE authentication and administrator privileges to create and
revoke sessions. QRMI 0.26.1 and later load the MUNGE library at runtime, so the
PyPI `qrmi` package installed by default works with the MUNGE daemon in the
containers. This setup was tested with QRMI 0.26.3.

To use another QRMI build, for an existing container cluster, copy the wheel into
`./shared` next to `docker-compose.yml`, where all nodes see it as `/shared`:

```bash
cp /path/to/qrmi-wheel.whl shared/
docker exec lsf-head /opt/lsfce/pyenv/bin/pip install --force-reinstall /shared/qrmi-wheel.whl
docker exec lsf-head /home/lsfuser/pyenv/bin/pip install --force-reinstall /shared/qrmi-wheel.whl
```

Replace `qrmi-wheel.whl` with the wheel's full filename. For a fresh installation,
the build argument `LSF_QRMI_PACKAGE` can specify a wheel URL or a wheel path visible
inside the container, such as `/shared/qrmi-wheel.whl`.

The containers run MUNGE with a key generated at first startup and shared through
the `munge_config` volume. Configure Warden's MUNGE daemon with the same key, or
copy the existing Warden MUNGE key into that volume as an administrator and
restart MUNGE on all LSF nodes, for example
`for c in lsf-head compute01 compute02; do docker exec $c service munge restart; done`.
Keep the key owned by `munge`, mode `0400`. The
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

## Environment Variables

| Environment Variable         | Description |
|------------------------------|-------------|
| Build/Installation Variables |             |
| `LSF_TAR`                    | Filename of the IBM LSF Community Edition distribution archive used by `install-lsf.sh` |
| `LSF_ENVDIR`                 | LSF environment directory containing runtime configuration files, startup scripts, hooks, and profiles |
| User Variables               |             |
| `QRMI_QPU_RESOURCES`         | Requested quantum resources |
| `QRMI_DELIMITER`             | Delimiter for `QRMI_QPU_RESOURCES`, `QRMI_JOB_QPU_RESOURCES`, `QRMI_JOB_QPU_TYPES` |
| `QRMI_IBM_QRS_IAM_APIKEY `   | IBM Quantum Platform API key |
| `LSF_QRMI_DEBUG`             | Enable debug output |
| JOB_STARTER Variables        |             |
| `QRMI_JOB_QPU_RESOURCES`     | Resources acquired by QRMI |
| `QRMI_JOB_QPU_TYPES`         | Acquired resource types |

## Links

[Setup with Docker, Podman (rootful or rootless) and Windows/WSL2](SETUP.md)

[IBM LFS Community Edition (free after a simple registration process)](https://early-access.ibm.com/software/support/trial/cst/programwebsite.wss?siteId=680&h=&tabId=&_gl=1*18pgo3p*_ga*ODgwNjAzMzMzLjE3OTEyOTM1ODI.*_ga_FYECCCS21D*czE3OTEyOTM1ODEkbzEkZzEkdDE3OTEyOTM2NjUkajQ4JGwwJGgw)

[QRMI Project](https://github.com/qiskit-community/qrmi/)

[QRMI Community Projects](https://github.com/qrmi-community/)

[QRMI Community Documentation](https://qrmi-community.github.io/)
