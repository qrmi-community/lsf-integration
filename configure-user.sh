#!/bin/bash

set -e

CONFDIR="/opt/lsfce/conf"

echo "$0: Set up lsfuser examples, venv"
cp -r /distribution/examples /home/lsfuser
chmod +x /home/lsfuser/examples/*.sh
python3 -m venv /home/lsfuser/pyenv
source /home/lsfuser/pyenv/bin/activate
pip install --upgrade pip
pip install dotenv numpy requests "${LSF_QRMI_PACKAGE:-qrmi}" qiskit qiskit_ibm_runtime
chown -R lsfuser:lsfuser /home/lsfuser

echo "$0: Configure lsfadmin and lsfuser to source profile.lsf in .bashrc"
echo 'if [ -f /opt/lsfce/conf/profile.lsf ]; then . /opt/lsfce/conf/profile.lsf; fi' >> /home/lsfadmin/.bashrc
echo 'if [ -f /opt/lsfce/conf/profile.lsf ]; then . /opt/lsfce/conf/profile.lsf; fi' >> /home/lsfuser/.bashrc
