#!/usr/bin/env bash
# Run as root in the pinned Ubuntu 22.04 toolchain container.
set -euo pipefail
curl -fsSL https://packages.osrfoundation.org/gazebo.gpg -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
printf '%s\n' 'deb [arch=amd64 signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable jammy main' > /etc/apt/sources.list.d/gazebo-stable.list
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gz-harmonic libunwind-dev
