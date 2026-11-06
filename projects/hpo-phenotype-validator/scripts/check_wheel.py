"""Install the wheel into a disposable environment and run outside the checkout."""

import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(command, directory):
    result = subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f"{command[0]} failed: {result.stderr[-1500:]}")
    return result.stdout.strip()


def main():
    wheels = list((ROOT / "dist").glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("Run uv build first; dist must contain exactly one wheel")
    with tempfile.TemporaryDirectory(prefix="hpo-wheel-check-") as directory:
        folder = Path(directory)
        env = folder / "env"
        run(["uv", "venv", str(env)], folder)
        run(
            [
                "uv",
                "pip",
                "install",
                "--no-deps",
                "--python",
                str(env / "bin/python"),
                str(wheels[0]),
            ],
            folder,
        )
        print(
            run(
                [
                    str(env / "bin/hpo-validate"),
                    "validate",
                    str(ROOT / "examples/accepted.json"),
                    "--out",
                    str(folder / "out"),
                ],
                folder,
            )
        )
        packet = json.loads((folder / "out/phenopacket.json").read_text())
        assert len(packet["phenotypicFeatures"]) == 4
    print(
        "Wheel smoke passed: bundled ontology found outside checkout; temporary environment removed."
    )


if __name__ == "__main__":
    main()
