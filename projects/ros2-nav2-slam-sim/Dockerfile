FROM --platform=linux/amd64 ros:humble-ros-base-jammy@sha256:a3f4de78e42cca693a543ece5798aedcf1cae0171fe71c334a047332cc72ef93
SHELL ["/bin/bash", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-navigation2 ros-humble-nav2-bringup ros-humble-nav2-simple-commander \
    ros-humble-slam-toolbox ros-humble-gazebo-ros-pkgs \
    ros-humble-launch-testing ros-humble-launch-testing-ros \
    python3-pytest python3-yaml python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /ws
COPY . /ws/src/lab_patrol
WORKDIR /ws/src/lab_patrol
CMD ["bash", "scripts/ci.sh", "7"]
