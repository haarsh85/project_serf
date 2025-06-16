FROM ubuntu:24.04

# Update the package list and install essential packages
RUN apt update && apt install -y \
    iproute2 \
    iputils-ping \
    net-tools \
    traceroute \
    vim \
    curl \
    ethtool \
    sockperf \
    iperf \
    iperf3 \
    netcat-openbsd \
    tcpdump \
    nmap \
    && apt clean && rm -rf /var/lib/apt/lists/*
    
# Set the default command to bash
CMD ["bash"]
