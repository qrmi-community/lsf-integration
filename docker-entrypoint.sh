#!/bin/bash
set -euo pipefail

ROLE="${NODE_ROLE:-compute}"

echo "Starting node $(hostname) with Role: ${ROLE}"

# All nodes require ssh
service ssh start

# Queue-level hooks manage Warden sessions as root; JOB_STARTER stays the job user.
printf 'LSF_ADMINS=lsfadmin\nLSB_PRE_POST_EXEC_USER=root\n' > /etc/lsf.sudoers
chmod 600 /etc/lsf.sudoers
install -d -m 711 -o root -g root /run/lsf-qrmi

if [ "${ROLE}" = "head" ] && [ ! -f /etc/munge/munge.key ]; then
    mungekey --create
fi
until [ -f /etc/munge/munge.key ]; do sleep 2; done
chown munge:munge /etc/munge/munge.key
chmod 400 /etc/munge/munge.key
service munge start

# Cluster installation on head node
if [ "${ROLE}" = "head" ] && [ ! -f /opt/lsfce/.cluster_ready ]; then
    echo "Installing and configuring LSF..."
    /usr/local/bin/install-lsf.sh
    /usr/local/bin/configure-lsf.sh
    /usr/local/bin/configure-user.sh
    touch /opt/lsfce/.cluster_ready
    echo "Cluster configuration complete"
fi

# All nodes should wait
echo "Waiting for environment dependencies..."
until [ -f /opt/lsfce/.cluster_ready ] && [ -f /opt/lsfce/conf/profile.lsf ]; do
    sleep 2
done
# On a restart, the shared install may be ready before Docker registers the peers.
until getent hosts lsf-head compute01 compute02 >/dev/null; do sleep 2; done

# Safely source profile without triggering 'set -e' via grep failures
set +e; source /opt/lsfce/conf/profile.lsf; set -e

# Compute nodes wait for master daemons
if [ "${ROLE}" = "compute" ]; then
    until lsid >/dev/null 2>&1; do sleep 2; done
fi

# Start LSF services
echo "Starting LSF daemons..."
lsadmin limstartup
lsadmin resstartup
badmin hstartup

# Ensure this node is alive
until lsload >/dev/null 2>&1; do sleep 2; done

echo "LSF ${ROLE} node ready. Container initialization complete."
exec tail -f /dev/null
