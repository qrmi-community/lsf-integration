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
cp /distribution/jobstarter.qrmi /opt/lsfce/10.1/linux3.12-glibc2.17-armv8/etc
cp /distribution/postexec.qrmi /opt/lsfce/10.1/linux3.12-glibc2.17-armv8/etc
cp ${CONFDIR}/lsbatch/cluster1/configdir/lsb.queues ${CONFDIR}/lsbatch/cluster1/configdir/lsb.queues.orig
sed -e "s/^QUEUE_NAME   = normal$/QUEUE_NAME   = normal\nJOB_STARTER  = \/opt\/lsfce\/10.1\/linux3.12-glibc2.17-armv8\/etc\/jobstarter.qrmi\nPOST_EXEC    = \/opt\/lsfce\/10.1\/linux3.12-glibc2.17-armv8\/etc\/postexec.qrmi/g" -e "s/^QUEUE_NAME   = interactive$/QUEUE_NAME   = interactive\nJOB_STARTER  = \/opt\/lsfce\/10.1\/linux3.12-glibc2.17-armv8\/etc\/jobstarter.qrmi\nPOST_EXEC    = \/opt\/lsfce\/10.1\/linux3.12-glibc2.17-armv8\/etc\/postexec.qrmi/g" ${CONFDIR}/lsbatch/cluster1/configdir/lsb.queues > /tmp/lsb.queues
cp /tmp/lsb.queues ${CONFDIR}/lsbatch/cluster1/configdir/lsb.queues

echo "$0: Install QRMI venv for hooks"
python3 -m venv /opt/lsfce/pyenv
source /opt/lsfce/pyenv/bin/activate
pip install --upgrade pip
pip install requests dotenv qrmi

echo "$0: Set lsfadmin as the owner"
chown -R lsfadmin:lsfadmin /opt/lsfce
