# FORGE-CANARY-BEGIN
# FORGE-CANARY-SLOT-1: 75e76ad5fdc1c20433fc50803c285f8cb69ca3c139ea082b87adb476602d96f0
# FORGE-CANARY-END
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_ENV_ROOT = _PACKAGE_ROOT / "environment"
_SOLUTION_ROOT = _PACKAGE_ROOT / "solution"
for _root in (_ENV_ROOT, _SOLUTION_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from raven_ar9 import _oracle_replay as replay

DEFAULT_EVENTLOG = "logs/artifacts/eventlog.json"


def _grader_path() -> Path | None:
    for candidate in (Path(__file__).resolve().parents[1] / "tests" / "score.py", Path("/tests/score.py")):
        if candidate.is_file():
            return candidate
    return None


def self_check(artifact: Path, mode: str) -> dict:
    """Score the written artifact with the shipped grader. tests/score.py is the only checker:
    the driver asserts nothing of its own, so the author-side repro and the delivered verifier
    cannot disagree. The grader JSON is written beside the artifact as score.json."""
    grader = _grader_path()
    workspace = artifact.parent
    if grader is None:
        return {"mode": mode, "skipped": "tests/score.py not found beside solution/"}
    out = workspace / "score.json"
    proc = subprocess.run(
        [sys.executable, str(grader), "--workspace", str(workspace), "--out", str(out)],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0 or not out.is_file():
        return {"mode": mode, "grader_exit": proc.returncode, "stderr": proc.stderr[-2000:]}
    result = json.loads(out.read_text(encoding="utf-8"))
    result["mode"] = mode
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    mode = "oracle"
    rest = []
    for arg in args:
        if arg.startswith("--mode="):
            mode = arg.split("=", 1)[1]
        else:
            rest.append(arg)
    target = Path(rest[0]) if rest else Path(DEFAULT_EVENTLOG)
    seed = int(rest[1]) if len(rest) > 1 else None
    payload = replay.run_mode(mode, seed)
    written = replay._write(target, payload)
    print(f"mode={mode} seed={payload['seed']} wrote {written}")
    result = self_check(written, mode)
    summary = {k: result.get(k) for k in ("reward", "full_success", "det_earned", "denom", "F", "skipped", "grader_exit")}
    print(json.dumps(summary, indent=2, default=str))
    if "skipped" in result:
        return 0
    if "grader_exit" in result:
        print(f"UNEXPECTED: grader failed on mode {mode}: {result.get('stderr', '')}")
        return 1
    want = replay.expected_full_success(mode)
    got = bool(result.get("full_success"))
    if got != want:
        print(f"UNEXPECTED: mode {mode} full_success={got}, wanted {want}")
        return 1
    if mode == "noop" and float(result.get("reward") or 0.0) != 0.0:
        print(f"UNEXPECTED: mode noop reward={result.get('reward')}, wanted 0.0")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
