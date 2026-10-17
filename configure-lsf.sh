#!/bin/bash

set -e

CONFDIR="/opt/lsfce/conf"

echo "$0: Configure lsf.conf to disable eauth and to use ssh instead of rsh"
cp ${CONFDIR}/lsf.conf ${CONFDIR}/lsf.conf.orig
sed "s/^LSF_AUTH=eauth$/LSF_AUTH=none/g" ${CONFDIR}/lsf.conf > /tmp/lsf.conf
cp /tmp/lsf.conf ${CONFDIR}/lsf.conf
cat >> ${CONFDIR}/lsf.conf <<EOF
LSF_REMOTE_COPY="scp -B"
LSF_RSH="ssh"
EOF

echo "$0: Configure lsb.hosts to not allow any jobs to run on lsf-head"
# Alternately, can specify HOSTS in ${CONFDIR}/lsbatch/cluster1/configdir/lsb.queues
cp ${CONFDIR}/lsbatch/cluster1/configdir/lsb.hosts ${CONFDIR}/lsbatch/cluster1/configdir/lsb.hosts.orig
sed "s/^End Host$/lsf-head   0    ()      ()    ()     ()     ()            (Y)\nEnd Host/g" ${CONFDIR}/lsbatch/cluster1/configdir/lsb.hosts > /tmp/lsb.hosts
cp /tmp/lsb.hosts ${CONFDIR}/lsbatch/cluster1/configdir/lsb.hosts

echo "$0: Install QRMI hooks"
mkdir -p /opt/lsfce/conf/hooks
cp /distribution/jobstarter.qrmi /distribution/pasqal_local.py /opt/lsfce/conf/hooks
chmod 755 /opt/lsfce/conf/hooks/jobstarter.qrmi /opt/lsfce/conf/hooks/pasqal_local.py
# Set JOB_STARTER, REQUEUE_EXIT_VALUES, MAX_JOB_REQUEUE for the
# normal and interactive queues
cp ${CONFDIR}/lsbatch/cluster1/configdir/lsb.queues ${CONFDIR}/lsbatch/cluster1/configdir/lsb.queues.orig
sed -e "s/^QUEUE_NAME   = normal$/QUEUE_NAME   = normal\nJOB_STARTER  = \/opt\/lsfce\/conf\/hooks\/jobstarter.qrmi\nREQUEUE_EXIT_VALUES = 99\nMAX_JOB_REQUEUE = 3/g" -e "s/^QUEUE_NAME   = interactive$/QUEUE_NAME   = interactive\nJOB_STARTER  = \/opt\/lsfce\/conf\/hooks\/jobstarter.qrmi\nREQUEUE_EXIT_VALUES = 99\nMAX_JOB_REQUEUE = 3/g" ${CONFDIR}/lsbatch/cluster1/configdir/lsb.queues > /tmp/lsb.queues
cp /tmp/lsb.queues ${CONFDIR}/lsbatch/cluster1/configdir/lsb.queues
sed -i '/^JOB_STARTER  =/a PRE_EXEC = /opt/lsfce/conf/hooks/pasqal_local.py acquire\nPOST_EXEC = /opt/lsfce/conf/hooks/pasqal_local.py release' \
    ${CONFDIR}/lsbatch/cluster1/configdir/lsb.queues

echo "$0: Copy publically accessible qrmi_config.json in LSF_ENVDIR"
cp /distribution/qrmi_config.json ${CONFDIR}

echo "$0: Install QRMI venv for hooks"
python3 -m venv /opt/lsfce/pyenv
source /opt/lsfce/pyenv/bin/activate
pip install --upgrade pip
pip install requests dotenv "${LSF_QRMI_PACKAGE:-qrmi}"

echo "$0: Set lsfadmin as the owner"
chown -R lsfadmin:lsfadmin /opt/lsfce
# The privileged hooks and their imports must not be writable by job users.
chown root:root /opt/lsfce ${CONFDIR} ${CONFDIR}/qrmi_config.json
chown -R root:root ${CONFDIR}/hooks /opt/lsfce/pyenv
