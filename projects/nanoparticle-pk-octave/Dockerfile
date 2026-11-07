# The same base and packages are used by GitHub Actions.
FROM ubuntu:24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    octave gnuplot-nox ghostscript fonts-freefont-otf ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
COPY . .
ENV GNUTERM=pngcairo
CMD ["sh", "-c", "octave --no-gui --quiet scripts/run_tests.m && octave --no-gui --quiet scripts/regenerate_all.m"]
