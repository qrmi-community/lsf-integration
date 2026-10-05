FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y \
        openssh-server \
        openssh-client \
        sudo \
        vim \
        curl \
        wget \
        rsync \
        net-tools \
        iproute2 \
        iputils-ping \
        procps \
        python3 \
        python3-pip \
        python3-venv \
        default-jre \
        ed \
        less \
        mpich \
        libmpich-dev && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/run/sshd
RUN ssh-keygen -A

RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config

RUN echo "    StrictHostKeyChecking no" >> /etc/ssh/ssh_config && \
    echo "    UserKnownHostsFile /dev/null" >> /etc/ssh/ssh_config

# Create lsfadmin with explicit UID/GID 1001
RUN groupadd -g 1001 lsfadmin && \
    useradd -u 1001 -g 1001 -m -s /bin/bash lsfadmin

# Create lsfuser with explicit UID/GID 1002 (no admin privileges)
RUN groupadd -g 1002 lsfuser && \
    useradd -u 1002 -g 1002 -m -s /bin/bash lsfuser

RUN echo "root:root" | chpasswd

COPY lsfsce10.2.0.15-armv8.tar.Z /distribution/

COPY docker-entrypoint.sh /usr/local/bin
COPY install-lsf.sh /usr/local/bin
COPY configure-lsf.sh /usr/local/bin

RUN chmod +x \
    /usr/local/bin/docker-entrypoint.sh \
    /usr/local/bin/install-lsf.sh \
    /usr/local/bin/configure-lsf.sh

COPY jobstarter.qrmi /distribution
COPY postexec.qrmi /distribution

COPY qrmi_config.json.example /distribution
COPY examples/ /distribution/examples/

CMD ["/usr/local/bin/docker-entrypoint.sh"]
