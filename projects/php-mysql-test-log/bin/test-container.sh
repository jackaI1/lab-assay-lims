#!/bin/sh
set -eu
# An isolated project owns only ephemeral test containers. Never touches saved readings.
project="testlog-check-$$"
cleanup() { docker compose -p "$project" --profile test down --volumes --remove-orphans >/dev/null; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
echo "Owned test project: $project; cleanup: docker compose -p $project --profile test down --volumes --remove-orphans"
docker compose --progress plain -p "$project" --profile test build tests
docker compose -p "$project" --profile test up -d --wait db-test
docker compose -p "$project" --profile test ps -q db-test | while read -r container; do
    docker inspect --format 'Owned database: {{.Name}} PID={{.State.Pid}} started={{.State.StartedAt}} ports={{json .NetworkSettings.Ports}}' "$container"
done
docker compose -p "$project" --profile test run --no-deps --rm tests
