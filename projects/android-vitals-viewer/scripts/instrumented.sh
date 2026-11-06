#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY_CHECK'
import socket
with socket.socket() as probe:
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    probe.bind(("127.0.0.1", 8000))  # Refuse to reuse somebody else's listener.
PY_CHECK
# This shell owns exactly this PID and port. The emulator is owned by the action.
.venv/bin/python -m uvicorn sandbox.server:app --host 127.0.0.1 --port 8000 --no-access-log > /tmp/vitals-sandbox.log 2>&1 &
sandbox_pid=$!
cleanup() {
  kill -TERM "$sandbox_pid" 2>/dev/null || true
  wait "$sandbox_pid" 2>/dev/null || true
  adb reverse --remove tcp:8000 || true
  if kill -0 "$sandbox_pid" 2>/dev/null; then echo 'Sandbox did not stop'; exit 1; fi
  if curl --silent --fail http://localhost:8000/health >/dev/null; then echo 'Port 8000 is still serving'; exit 1; fi
}
trap cleanup EXIT
echo "Owned sandbox PID=$sandbox_pid port=8000 cleanup=kill -TERM $sandbox_pid"
ps -p "$sandbox_pid" -o pid,lstart,command
for attempt in $(seq 1 30); do
  if curl --silent --fail http://localhost:8000/health >/dev/null; then break; fi
  sleep 1
done
curl --silent --fail http://localhost:8000/health
adb reverse tcp:8000 tcp:8000
./gradlew --no-daemon connectedDebugAndroidTest

mkdir -p app/build/reports/screenshots
python3 - <<'PY_SCREENSHOT'
from pathlib import Path
import shutil
images = list(Path('app/build/outputs/connected_android_test_additional_output').rglob('vitals.png'))
assert images, 'The bridge journey screenshot was not collected'
shutil.copy2(images[0], 'app/build/reports/screenshots/vitals.png')
PY_SCREENSHOT
