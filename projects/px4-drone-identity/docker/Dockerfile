FROM ubuntu:24.04 AS toolchain
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 LC_ALL=C.UTF-8
RUN apt-get update -qq && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
# Immutable source behind the PX4 v1.16.0 release tag.
ARG PX4_COMMIT=6ea3539157ca358c70a515878b77077af7d4611d
RUN git clone --branch v1.16.0 --depth 1 https://github.com/PX4/PX4-Autopilot.git /opt/PX4 \
    && test "$(git -C /opt/PX4 rev-parse HEAD)" = "$PX4_COMMIT" \
    && touch /.dockerenv \
    && bash /opt/PX4/Tools/setup/ubuntu.sh --no-nuttx \
    && rm -rf /var/lib/apt/lists/* /root/.cache/pip
FROM toolchain AS firmware
COPY docker/loopback.patch /tmp/loopback.patch
RUN cd /opt/PX4 && git apply --check /tmp/loopback.patch && git apply /tmp/loopback.patch \
    && git submodule update --init --recursive --depth 1 Tools/simulation/gz \
    && test -f Tools/simulation/gz/worlds/default.sdf
COPY px4/identity_guard /opt/PX4/src/modules/identity_guard
RUN cp /opt/PX4/src/modules/identity_guard/IdentityStatus.msg /opt/PX4/msg/IdentityStatus.msg \
    && sed -i '/^set(msg_files$/a\    IdentityStatus.msg' /opt/PX4/msg/CMakeLists.txt \
    && printf '\nCONFIG_MODULES_IDENTITY_GUARD=y\n' >> /opt/PX4/boards/px4/sitl/default.px4board \
    && cd /opt/PX4 && make -j2 px4_sitl_default
COPY docker/px4-rc.mavlink /opt/PX4/ROMFS/px4fmu_common/init.d-posix/px4-rc.mavlink
# PX4's ROMFS copy stamp does not track individual script edits. Stage the
# lab script explicitly into the generated runtime tree as well as the source.
RUN cp /opt/PX4/ROMFS/px4fmu_common/init.d-posix/px4-rc.mavlink \
       /opt/PX4/build/px4_sitl_default/etc/init.d-posix/px4-rc.mavlink \
    && cmp /opt/PX4/ROMFS/px4fmu_common/init.d-posix/px4-rc.mavlink \
           /opt/PX4/build/px4_sitl_default/etc/init.d-posix/px4-rc.mavlink \
    && cmake --build /opt/PX4/build/px4_sitl_default --target px4_gz_plugins --parallel 2
FROM firmware AS runtime
RUN apt-get update -qq && apt-get install -y --no-install-recommends python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/identity-venv
WORKDIR /app
COPY pyproject.toml /app/
COPY src /app/src
COPY tests /app/tests
RUN /opt/identity-venv/bin/pip install '.[test]'
ENV HEADLESS=1 MAVLINK20=1
ENTRYPOINT ["/opt/identity-venv/bin/python", "-m", "drone_identity.cli"]
CMD ["experiments", "--output", "/results"]
