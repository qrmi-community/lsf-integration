# lsf-integration

The "original" LSF-QRMI project is located at https://github.ibm.com/QCHPC/lsf-qpu/ and now https://github.ibm.com/IBM/lsf-qrmi. This repository is an updated version that uses LSF Community Edition (see link below) in multiple containers and moves the integration to the usual acquire-execute-release pattern. The multiple containers include a management/login node (lsf-head) and two compute nodes (compute01 and compute02). The acquire-execute is performed in a jobstarter hook (jobstarter.qrmi), and the release is performed in a postexec hook (postexec.qrmi). Following the usual acquire-execute-release pattern allows jobs to be cancelled properly even when the job is hard killed.

The hooks are expecting QRMI_QPU_RESOURCES and optionally LSF_QRMI_DEBUG to be defined when running bsub (example below).

```
QRMI_QPU_RESOURCES=ibm_marrakesh LSF_QRMI_DEBUG=1 bsub -Is ./run_sampler.sh
```

Note that $HOME/qrmi_config.json does not follow the design pattern established by the Slurm-QRMI integration. The Slurm-QRMI integration uses a system-wide qrmi_config.json only accessible by administrators. Because the LSF jobstarter hook runs as the user, qrmi_config.json must be accessible by the user.

## Instructions

```
# Bring down volumes for a clean slate
podman compose down --volumes
podman compose up --build
podman exec -it -u lsfuser -w /home/lsfuser lsf-head bash
cp qrmi_config.json.example qrmi_config.json
# Populate qrmi_config.json appropriately
# Simple interactive test
bsub -Is hostname
# Simple quantum test
QRMI_QPU_RESOURCES=ibm_marrakesh LSF_QRMI_DEBUG=1 bsub -Is $HOME/examples/run_sampler.sh
```

## Links

[IBM LFS Community Edition (free after a simple registration process)](https://early-access.ibm.com/software/support/trial/cst/programwebsite.wss?siteId=680&h=&tabId=&_gl=1*18pgo3p*_ga*ODgwNjAzMzMzLjE3OTEyOTM1ODI.*_ga_FYECCCS21D*czE3OTEyOTM1ODEkbzEkZzEkdDE3OTEyOTM2NjUkajQ4JGwwJGgw)
