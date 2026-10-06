#!/bin/bash

set -e

CONFDIR="/opt/lsfce/conf"

echo "$0: Set up lsfuser qrmi_config.json, examples, venv"
cp /distribution/qrmi_config.json.example /home/lsfuser
cp -r /distribution/examples /home/lsfuser
chmod 600 /home/lsfuser/qrmi_config.json.example
python3 -m venv /home/lsfuser/pyenv
source /home/lsfuser/pyenv/bin/activate
pip install --upgrade pip
pip install dotenv numpy requests qrmi numpy qiskit qiskit_ibm_runtime
chown -R lsfuser:lsfuser /home/lsfuser

echo "$0: Configure lsfadmin and lsfuser to source profile.lsf in .bashrc"
echo 'if [ -f /opt/lsfce/conf/profile.lsf ]; then . /opt/lsfce/conf/profile.lsf; fi' >> /home/lsfadmin/.bashrc
echo 'if [ -f /opt/lsfce/conf/profile.lsf ]; then . /opt/lsfce/conf/profile.lsf; fi' >> /home/lsfuser/.bashrc
