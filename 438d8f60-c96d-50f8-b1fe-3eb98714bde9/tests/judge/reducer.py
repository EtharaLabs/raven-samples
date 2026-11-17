#!/usr/bin/env python3
# FORGE-CANARY-BEGIN
# FORGE-CANARY-SLOT-1: 633b35f53feb54275eaab88ee3952b92c4532372d9b127e89bfcfc79db250cf0
# FORGE-CANARY-END
"""Judge reducer: folds the per-criterion verdicts into a SUBTRACTIVE penalty.

The judged layer is subtractive capacity: it can dock the deterministic ceiling but
never raise it. reduce(compiled, verdicts) returns

    semantic_penalty = sum over APPLICABLE judged of weight * (1 - score) / DENOM

which tests/score.py subtracts from C_ceiling. A criterion is APPLICABLE only when its
deterministic prerequisite was EARNED in `compiled`; an inapplicable criterion owes no
verdict. For an APPLICABLE criterion a missing, malformed, out-of-range, non-finite or
boolean score is a HarnessFault, never a default and never a pass.

The numerator is accumulated and divided once, so the fold is exact rather than the
accumulation of per-criterion rounding.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

try:
    from score import HarnessFault
except ImportError:  # standalone use outside the verifier image

    class HarnessFault(RuntimeError):
        """A VERIFIER fault, never an agent failure."""


DENOM = 99
WEIGHTS = {
    'j_route_rationale': 1,
    'j_client_tone': 1,
    'j_confirm_truthful': 1,
}
PREREQUISITES = {
    'j_route_rationale': 'r1_route_booked',
    'j_client_tone': 'n1_client_notified',
    'j_confirm_truthful': 'cc_confirm_sent',
}


def applicability(compiled: dict | None) -> dict[str, bool]:
    """APPLICABLE iff the deterministic prerequisite was earned (judge_output_policy)."""
    records = compiled or {}
    return {
        item_id: bool((records.get(prerequisite) or {}).get('earned'))
        for item_id, prerequisite in PREREQUISITES.items()
    }


def _validate(item_id: str, raw: object) -> float:
    if isinstance(raw, dict):
        if 'score' not in raw:
            raise HarnessFault(f'judge verdict for {item_id} carries no score field')
        raw = raw['score']
    if raw is None:
        raise HarnessFault(f'judge verdict for applicable criterion {item_id} is missing')
    if isinstance(raw, bool):
        raise HarnessFault(
            f'judge verdict for {item_id} is a bool ({raw!r}); a continuous score in [0,1] is required'
        )
    if not isinstance(raw, (int, float)):
        raise HarnessFault(f'judge verdict for {item_id} is malformed: {raw!r}')
    value = float(raw)
    if not math.isfinite(value):
        raise HarnessFault(f'judge verdict for {item_id} is non-finite: {value!r}')
    if value < 0.0 or value > 1.0:
        raise HarnessFault(f'judge verdict for {item_id} is out of range [0,1]: {value!r}')
    return value


def reduce(compiled: dict | None, verdicts: dict | None) -> dict:
    if not isinstance(verdicts, dict):
        raise HarnessFault(
            f'judge verdicts must be an object, got {type(verdicts).__name__}'
        )
    unknown = sorted(k for k in verdicts if k not in WEIGHTS)
    if unknown:
        raise HarnessFault(f'judge verdicts carry unknown criterion ids: {unknown}')
    applicable = applicability(compiled)
    numerator = 0.0
    scores: dict[str, float] = {}
    for item_id, weight in WEIGHTS.items():
        if not applicable[item_id]:
            continue
        if item_id not in verdicts:
            raise HarnessFault(
                f'judge verdict for applicable criterion {item_id} is missing; a '
                'missing verdict is a harness failure, never a default pass'
            )
        value = _validate(item_id, verdicts[item_id])
        scores[item_id] = value
        numerator += weight * (1.0 - value)
    return {
        'semantic_penalty': numerator / DENOM,
        'denom': DENOM,
        'applicable': [k for k, v in applicable.items() if v],
        'inapplicable': [k for k, v in applicable.items() if not v],
        'scores': scores,
    }


def main() -> int:
    payload = json.loads(sys.stdin.read() or '{}')
    try:
        folded = reduce(payload.get('compiled'), payload.get('verdicts') or {})
    except HarnessFault as fault:
        print(json.dumps({'harness_failure': True, 'reason': str(fault)}), file=sys.stderr)
        return 3
    print(json.dumps(folded, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
