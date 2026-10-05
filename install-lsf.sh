#!/bin/bash

set -e

# Assuming we have LSF CE downloaded already
cd /distribution
tar --no-same-owner -xf lsfsce10.2.0.15-armv8.tar.Z
cd lsfsce10.2.0.15-armv8/lsf
tar --no-same-owner -xf lsf10.1_no_jre_lsfinstall.tar.Z
cd lsf10.1_lsfinstall

# Required for install
cat > install.config <<EOF
LSF_TOP="/opt/lsfce"
LSF_ADMINS="lsfadmin"
LSF_CLUSTER_NAME="cluster1"
LSF_MASTER_LIST="lsf-head compute01 compute02"
LSF_TARDIR="/distribution/lsfsce10.2.0.15-armv8/lsf/"
EOF

# "echo 1" accepts the LSF license
echo 1 | ./lsfinstall -f install.config
