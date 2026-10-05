# lsf-integration

The "original" LSF-QRMI project is located at https://github.ibm.com/QCHPC/lsf-qpu/. This repository is an updated version that uses LSF Community Edition (free at https://www.ibm.com/support/pages/where-do-i-download-lsf-community-edition) in multiple containers and moves the integration to the usual acquire-execute-release pattern. The multiple containers include a management/login node (lsf-head) and two compute nodes (compute01 and compute02). The acquire-execute is performed in a jobstarter hook (jobstarter.qrmi), and the release is performed in a postexec hook (postexec.qrmi). Following the usual acquire-execute-release pattern allows jobs to be cancelled properly.

The hooks are expecting QRMI_QPU_RESOURCES and optionally QRMI_QPU_RESOURCES_FILTER and LSF_QRMI_DEBUG to be defined when running bsub (example below).

```
QRMI_QPU_RESOURCES=ibm_marrakesh,ibm_inst1 QRMI_QPU_RESOURCES_FILTER="name=ibm_f*" LSF_QRMI_DEBUG=1 bsub -Is ./run_example.sh
```

```ibm_marrakesh``` and ```ibm_inst1``` are resources defined in $HOME/qrmi_config.json.  ```ibm_marrakesh``` is a static resource. ```ibm_inst1``` is a dynamic resource that will be filtered by the expression ```name=ibm_f*```. This filters out quantum system names such as ```ibm_kingston```. See https://github.com/qiskit-community/qrmi/pull/142 for additional details about dynamic resources.

Note that $HOME/qrmi_config.json does not follow the design pattern established by the Slurm-QRMI integration. The Slurm-QRMI integration uses a system-wide qrmi_config.json only accessible by administrators. Because the LSF jobstarter hook runs as the user, qrmi_config.json must be accessible by the user.

## Instructions

```
#podman compose down --volumes
podman compose up --build
podman exec -it -u lsfuser -w /home/lsfuser lsf-head bash
cp qrmi_config.json.example qrmi_config.json
# Populate qrmi_config.json appropriately
bsub -Is hostname # Simple interactive test
python3 -m venv $HOME/pyenv
source $HOME/pyenv/bin/activate
pip install --upgrade pip
pip install dotenv numpy requests qrmi numpy qiskit qiskit_ibm_runtime
QRMI_QPU_RESOURCES=ibm_marrakesh LSF_QRMI_DEBUG=1 bsub -Is $HOME/examples/run_sampler.sh
```
