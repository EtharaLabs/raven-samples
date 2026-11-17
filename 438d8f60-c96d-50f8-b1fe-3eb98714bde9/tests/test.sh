#!/bin/sh
# GENERATED from solution/grounding.yaml by solution/recompute.py. DO NOT HAND-EDIT.
# test.sh is not one of the canary carriers in _CANARY_FILES, so it carries no canary
# block: an unplanted all-zero slot is indistinguishable from a stripped one.
#
# Verifier entry point. score.py is the authority for the bound reward (C, F, R,
# full_success); it exits 3 on a harness failure so an unusable artifact or an invalid
# judge verdict fails loudly instead of scoring zero like a legitimate no-op.
# rewardkit then folds the 44 compiled criteria into the deterministic ceiling, det_earned/164.
#
# JUDGE POLICY (credential-conditioned, three states, no silent middle):
#   1. RAVEN_JUDGE_VERDICTS supplied, or a judge credential present (OPENAI_API_KEY,
#      non-empty) -> the in-flow judge runs and score.py folds the
#      verdicts under RAVEN_JUDGE_MODE=live. A credential that is present but unusable
#      fails LOUD (runner.py exits non-zero, the trap emits reward 0): a reachable-but-broken
#      judge must never be downgraded to the ungraded deterministic ceiling.
#   2. No verdicts and NO credential -> the judge is GATED, not broken. runner.py is not
#      invoked at all and score.py runs under RAVEN_JUDGE_MODE=gated: the judged layer
#      contributes no penalty, reports status=gated_pending, and the run scores the
#      deterministic ceiling (the reference therefore scores 1.0). This is the degrade
#      path a credential-free grader (meta-oracle / offline QC) must take; invoking a judge
#      that cannot possibly authenticate would turn an infrastructure absence into a 0.
#   3. No credential but RAVEN_REQUIRE_JUDGE set non-empty -> HARD ERROR, exit 1. This is
#      the real-QC/pilot setting: it makes a DROPPED secret fail loudly instead of silently
#      collecting the ungraded ceiling, so state 2 can never be reached by accident where a
#      judged score was contracted.
set -eu

WORKSPACE="${RAVEN_VERIFIER_WORKSPACE:-/logs/artifacts}"
OUT_DIR="${RAVEN_VERIFIER_OUT:-/logs/verifier}"
mkdir -p "$OUT_DIR"

# harbor-task-v2 requires a reward written to reward.txt (and reward.json) even on failure. score.py
# exits 3 on a harness failure; without this trap set -eu would leave no reward file, which Harbor
# records as a silent 0 indistinguishable from a legitimate no-op. The trap guarantees a 0 reward is
# emitted on any non-zero exit; the success path overwrites it with the bound value below.
emit_reward() {
    printf '%s' "$1" > "$OUT_DIR/reward.txt"
    printf '{"reward": %s}' "$1" > "$OUT_DIR/reward.json"
}
trap 'rc=$?; [ "$rc" -ne 0 ] && [ ! -s "$OUT_DIR/reward.txt" ] && emit_reward 0; exit $rc' EXIT
emit_reward 0

# A credential injected as an unset `--verifier-env KEY=${KEY}` template arrives as an EMPTY
# (or whitespace-only) value, which is exactly the dropped-secret case. Unquoted expansion
# word-splits such a value to zero fields, so this is a value test, not a set test.
has_value() {
    set -- ${1:-}
    [ "$#" -gt 0 ]
}

JUDGE_READY=0
if [ -n "${RAVEN_JUDGE_VERDICTS:-}" ]; then
    JUDGE_READY=1
elif has_value "${OPENAI_API_KEY:-}"; then
    JUDGE_READY=1
fi

if [ "$JUDGE_READY" -eq 0 ] && [ -n "${RAVEN_REQUIRE_JUDGE:-}" ]; then
    echo "FATAL: RAVEN_REQUIRE_JUDGE is set but no judge credential is present" >&2
    echo "(OPENAI_API_KEY is unset or empty) and no" >&2
    echo "RAVEN_JUDGE_VERDICTS were supplied. Refusing to score the ungraded" >&2
    echo "deterministic ceiling as if it were a judged result." >&2
    exit 1
fi

# In-flow judge (production path). The runner dials the judge model itself and writes verdicts,
# which score.py then folds -- so ONE test.sh run yields the complete compiled+judge reward.
# Auth: OPENAI_API_KEY (honouring OPENAI_BASE_URL for an OpenAI-compatible endpoint), injected
# by the harness at launch (see task.toml [verifier.environment]); never a literal in the
# bundle. set -eu + the EXIT trap make an unreachable judge fail loud instead of recording a pass.
if [ "$JUDGE_READY" -eq 1 ] && [ -z "${RAVEN_JUDGE_VERDICTS:-}" ]; then
    RAVEN_VERIFIER_WORKSPACE="$WORKSPACE" RAVEN_JUDGE_LIVE_OUT="$OUT_DIR/verdicts.json" \
        python /tests/judge/runner.py 1>&2
    RAVEN_JUDGE_VERDICTS="$OUT_DIR/verdicts.json"
fi

if [ -n "${RAVEN_JUDGE_VERDICTS:-}" ]; then
    # mode=live: score.py REFUSES to default a missing/null verdict set to a pass, so a judge
    # that wrote an empty verdicts file fails loud instead of silently degrading.
    RAVEN_JUDGE_MODE=live python /tests/score.py --workspace "$WORKSPACE" \
        --verdicts "$RAVEN_JUDGE_VERDICTS" --out "$OUT_DIR/score.json"
else
    # Gated degrade: semantic_penalty returns 0.0 with status=gated_pending, so
    # reward == det_earned/164 and the reference scores its full deterministic ceiling.
    RAVEN_JUDGE_MODE=gated python /tests/score.py --workspace "$WORKSPACE" \
        --out "$OUT_DIR/score.json"
fi

# score.py is the DECLARED authority for the bound reward: its score.json 'reward' is the
# complete fault-aware + judge-folded value. rewardkit (when it runs) only re-derives the
# deterministic COMPILED weighted-mean and CANNOT represent the fault budget or the subtractive
# judged layer, so its number is higher and WRONG as the headline. Therefore reward.json ALWAYS
# comes from score.json, never from rewardkit. rewardkit is run only to emit its diagnostic
# breakdown to a separate file; it must never author the canonical reward.
rewardkit /tests --workspace "$WORKSPACE" --output "$OUT_DIR/reward-details.json" 2>/dev/null || true
BOUND_REWARD="$(python -c 'import json, sys; print(json.load(open(sys.argv[1]))["reward"])' "$OUT_DIR/score.json")"
emit_reward "$BOUND_REWARD"
