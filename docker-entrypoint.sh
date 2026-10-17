#!/bin/bash
set -euo pipefail

ROLE="${NODE_ROLE:-compute}"

echo "Starting node $(hostname) with Role: ${ROLE}"

# All nodes require ssh
service ssh start

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

# Safely source profile without triggering 'set -e' via grep failures
set +e; source /opt/lsfce/conf/profile.lsf; set -e

# Compute nodes wait for master daemons
if [ "${ROLE}" = "compute" ]; then
    until lsid >/dev/null 2>&1; do sleep 2; done
fi

# Start LSF services
echo "Starting LSF daemons..."
# Start the daemons directly: lsadmin/badmin start them through bctrld, which
# refuses ("Permission denied") when root is inside a user namespace, as in
# rootless Podman. Running the daemons as root works with and without user
# namespaces.
"${LSF_SERVERDIR}/lim"
"${LSF_SERVERDIR}/res"
"${LSF_SERVERDIR}/sbatchd"

# Ensure this node is alive
until lsload >/dev/null 2>&1; do sleep 2; done

echo "LSF ${ROLE} node ready. Container initialization complete."
exec tail -f /dev/null
