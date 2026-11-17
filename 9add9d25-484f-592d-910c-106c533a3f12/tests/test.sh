#!/bin/sh
# Verifier entrypoint. rewardkit is baked into the verifier image at build time
# (tests/Dockerfile). Scanning /tests discovers both the compiled test_output dimension
# and the codex judge dimension; judge.toml [judge].weight collapses them 80:20. The judge
# calls the model over the allowlisted host at grade time.
#
# JUDGE-DEGRADATION LADDER (Meta Oracle + QC safe):
#   * Judge credential present -> full 80/20 grade; a genuine judge/grading error still
#     degrades to the compiled channel (never records a false pass, never a false 0).
#   * No judge credential at all (Meta Oracle context: reference solution is applied in an
#     env with no judge model) -> grade the deterministic test_output channel ALONE and
#     report its real value, exit 0, and drop a judge_unavailable.json sidecar. This is the
#     config fact "no judge configured", distinct from "judge configured but failed".
#   * RAVEN_REQUIRE_JUDGE set (QC/pilot launcher) + no credential -> HARD ERROR (exit 1):
#     closes the dropped-secret hole so a real grading run can never silently skip the judge.
set -u
OUT=/logs/verifier
mkdir -p "$OUT"

emit_reward() {
    printf '%s' "$1" > "$OUT/reward.txt"
    printf '{"reward": %s}' "$1" > "$OUT/reward.json"
}

# Always leave a reward behind, even on an unexpected exit, so Harbor never records a silent
# missing-reward as an error. The success paths below overwrite this seed with the real value.
trap 'rc=$?; [ -s "$OUT/reward.txt" ] || emit_reward 0; exit $rc' EXIT
emit_reward 0

promote() {
    python3 -c 'import json,sys; r=json.load(open(sys.argv[1]))["reward"]; open(sys.argv[2],"w").write(str(r))' \
        "$OUT/reward.json" "$OUT/reward.txt"
}

JUDGE_READY=1
if [ -z "${OPENAI_API_KEY:-}" ] && [ -z "${CODEX_ACCESS_TOKEN:-}" ]; then
    JUDGE_READY=0
fi

if [ "$JUDGE_READY" = "1" ]; then
    if rewardkit /tests --workspace "${HARBOR_WORKSPACE:-/app}" --output "$OUT/reward.json"; then
        promote
        exit 0
    fi
    echo "rewardkit (judge path) failed: degrading to the compiled test_output channel" >&2
else
    echo "no judge credential (OPENAI_API_KEY/CODEX_ACCESS_TOKEN unset): compiled-only grade" >&2
fi

# Degrade path. A QC/pilot run demands a live judge: fail loud instead of silently degrading.
if [ -n "${RAVEN_REQUIRE_JUDGE:-}" ]; then
    echo "RAVEN_REQUIRE_JUDGE set but no judge available: failing loud" >&2
    emit_reward 0
    exit 1
fi

# Record WHY the judged dimension was dropped (a sidecar file, never a key in reward.json).
printf '{"judge_unavailable": true, "reason": "no judge credential or judge grading error; graded compiled test_output channel only"}' \
    > "$OUT/judge_unavailable.json"

# Compiled-only grade: /tests/test_output has no non-dunder subdirs, so rewardkit discovers a
# single flat dimension (the deterministic score). The judged group is absent entirely.
if rewardkit /tests/test_output --workspace "${HARBOR_WORKSPACE:-/app}" --output "$OUT/reward.json"; then
    promote
else
    echo "compiled-only grade failed: emitting reward 0" >&2
    emit_reward 0
fi
exit 0
