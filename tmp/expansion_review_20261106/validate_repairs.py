"""Run each expansion test file in a fresh interpreter and preserve exact commands."""
import json
import subprocess
import sys
from pathlib import Path

out = Path(__file__).parent
results = []
with (out / "repair_tests.log").open("w", encoding="utf-8") as log:
    for path in sorted(Path("expansions").glob("**/src/test_*.py")):
        command = [sys.executable, "-m", "pytest", "-q", str(path), "-p", "no:cacheprovider"]
        result = subprocess.run(command, text=True, capture_output=True)
        log.write(json.dumps(command) + "\n" + result.stdout + result.stderr + "\n")
        log.flush()
        results.append({"command": command, "returncode": result.returncode, "output": result.stdout + result.stderr})
        print(path, result.returncode, flush=True)
(out / "repair_tests.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
sys.exit(any(r["returncode"] for r in results))
