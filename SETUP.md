# Setup: Docker, Podman and Windows (WSL2)

The cluster runs with Docker, rootful Podman and rootless Podman, on Linux,
macOS and Windows (WSL2). This page covers what differs between them. The
commands in [README.md](README.md) use `docker`; replace it with `podman` where
noted below.

## 1. Download LSF Community Edition

Follow [tutorial_downloads.md](tutorial_downloads.md). Put the archive in this
directory and check that it is the real archive, not an HTML page (about 2.4 GB
for x86_64):

```bash
gzip -t lsfsce10.2.0.15-x86_64.tar.Z && echo OK
```

## 2. Build and start

| Engine | Build | Start | Shell on the head node |
|--------|-------|-------|------------------------|
| Docker, Docker Desktop | `docker compose build --build-arg LSF_TAR=<archive>` | `docker compose up -d` | `docker exec -it -u lsfuser -w /home/lsfuser lsf-head bash` |
| Podman (rootless or rootful) | `podman compose build --build-arg LSF_TAR=<archive>` | `podman compose up -d` | `podman exec -it -u lsfuser -w /home/lsfuser lsf-head bash` |

`<archive>` is `lsfsce10.2.0.15-x86_64.tar.Z` on Intel/AMD and
`lsfsce10.2.0.15-armv8.tar.Z` on Apple silicon.

The first start of `lsf-head` installs LSF and the Python environments (several
minutes). The cluster is ready when `podman logs compute02` (or `docker logs`)
ends with `LSF compute node ready`. Then, as `lsfuser`:

```bash
bsub -Is hostname
```

The LSF commands are on the `PATH` in interactive shells, because `.bashrc`
sources `/opt/lsfce/conf/profile.lsf`. For non-interactive commands, such as
`podman exec lsf-head bash -c ...`, source that file first.

Stop with `compose down`. `compose down -v` also deletes the volumes (LSF
installation, home directories, MUNGE key) for a completely fresh start.

## 3. Rootless Podman

Podman runs rootless by default when started by a normal user: on Linux,
including WSL2, and in the default `podman machine` on macOS and Windows. Root
inside a rootless container is mapped to an unprivileged user on the host
through a user namespace.

LSF's daemon control commands (`lsadmin limstartup`, `lsadmin resstartup`,
`badmin hstartup`) start the daemons through `bctrld`. `bctrld` reads
`/proc/self/uid_map` and refuses with `Permission denied` when root is inside a
user namespace. Therefore `docker-entrypoint.sh` starts `lim`, `res` and
`sbatchd` directly from `$LSF_SERVERDIR` as root; `sbatchd` starts `mbatchd` on
the master. This is the same set of daemons and works with and without user
namespaces, so no rootful setup is needed.

Other notes for Podman:

- **Compose provider.** `podman compose` runs an external provider. On Ubuntu,
  install `podman-compose` (`sudo apt install podman podman-compose`). The
  Ubuntu `docker-compose` package is the old v1, needs the Podman API socket
  and also installs the Docker engine (`docker.io`).
- **Start order.** `podman-compose` 1.0.x does not wait for
  `condition: service_completed_successfully`, so `lsf-head` can start before
  `ssh-generator` has finished. The keys are created within seconds, before LSF
  needs them.
- **Host names.** `bhosts` shows compute nodes with Podman's DNS suffix (for
  example `compute01.dns.podman`). Jobs are dispatched normally.

## 4. Windows (WSL2)

Linux containers on Windows always run in a Linux VM. On Windows Home (no
Hyper-V) that is WSL2, also for Docker Desktop and Podman Desktop. The simplest
setup is to run everything from an Ubuntu shell in WSL2.

1. Install Ubuntu 24.04: `wsl --install Ubuntu-24.04` (PowerShell).
2. In Ubuntu, install a container engine, for example
   `sudo apt install podman podman-compose`. Docker Engine inside WSL, or Docker
   Desktop with WSL integration, also works.
3. Clone this repository and download the LSF archive inside the WSL file system
   (for example `~/lsf-integration`), not under `/mnt/c`. Windows paths are slow
   for builds and do not keep Linux permissions.
4. Build and start as in section 2.

From PowerShell, open a shell on the head node with:

```powershell
wsl -e podman exec -it -u lsfuser -w /home/lsfuser lsf-head bash
```

Troubleshooting on WSL2:

- **`default OCI runtime "crun" not found` or `RunRoot ... is not writable`.**
  The systemd user session (`/run/user/<uid>`) was not started, which rootless
  Podman needs. Enable lingering once, so it is always started:
  `sudo loginctl enable-linger $USER`.
- **`python3 -m venv` fails** (`ensurepip is not available`): Ubuntu needs
  `sudo apt install python3-venv` for virtual environments on the WSL host.
  Inside the containers this is already installed.
- **Disk space.** The WSL virtual disk grows but does not shrink by itself.
  After `podman system prune -a`, compact it with `diskpart` (`select vdisk
  file=<path to ext4.vhdx>`, `attach vdisk readonly`, `compact vdisk`, `detach
  vdisk`) after `wsl --shutdown`, from an Administrator PowerShell.

## 5. Resources

Tested on Windows 11 Home with WSL2 (Ubuntu 24.04, rootless Podman 4.9.3,
podman-compose 1.0.6), 2 CPUs and 2.8 GB of memory for WSL:

| Step | Time / size |
|------|-------------|
| Build from scratch (3 services; the 2nd and 3rd come from the cache) | about 17 minutes (45 at low CPU priority) |
| Images (shared layers) | about 4 GB |
| First start until `LSF compute node ready` (LSF install, `pip` downloads) | about 6 minutes |
| Memory of the running, idle cluster | about 250 MB |
| Disk used in WSL during the test, including the archive | about 14 GB |
