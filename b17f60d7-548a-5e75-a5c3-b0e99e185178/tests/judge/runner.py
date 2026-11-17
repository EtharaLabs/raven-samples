#!/usr/bin/env python3
# FORGE-CANARY-BEGIN
# FORGE-CANARY-SLOT-1: 0aed3c0430e79fda72a8e97fadc4f7ce83cdd0766f86a0401f27523e4d45c855
# FORGE-CANARY-END
"""Judge runner: builds the judgment request set for the shipped judged criteria.

One request per judged criterion, for a judge host to consume. Live model calls are
S5-gated: packet.json carries live_calls_enabled=false and require_live_gate_open()
raises while the gate is shut, so this runner can never invent a verdict. The model,
temperature, score range and judgment ids are read from packet.json; the criterion
table below is derived from the approved rubric.
"""
from __future__ import annotations

import json
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


PACKET = json.loads((_HERE / 'packet.json').read_text(encoding='utf-8'))
LIVE_CALLS_ENABLED = bool(PACKET.get('live_calls_enabled'))
JUDGED = (
    ('j_o5_quality', 1, 'o5_contains_time'),
    ('j_o6_truthful', 1, 'o6_sent'),
    ('j_reschedule_correct', 1, 'o1_start'),
    ('j_handoff', 1, 'o6_sent'),
    ('j_notify_consistent', 1, 'o5_contains_time'),
    ('j_agenda_quality', 1, 'o10_complete'),
    ('j_adaptation_coherent', 1, 'a2_rebooked'),
    ('j_agenda_addendum_prose', 1, 'a6_addendum_applied'),
    ('j_role_channel_tone', 1, 'x1_channel_resolved'),
    ('j_ride_replan_legible', 1, 'a5_ride_rebooked'),
    ('j_procurement_rationale', 1, 'x5_product'),
)


def require_live_gate_open() -> None:
    """Raise while S5-live is gated; a caller must never reach a model through this."""
    if not LIVE_CALLS_ENABLED:
        raise HarnessFault(
            PACKET.get('live_gate')
            or 'live judge calls are S5-gated for this bundle'
        )


def build_requests() -> list[dict]:
    shipped = set(PACKET.get('judgments') or {})
    declared = {item_id for item_id, _weight, _prerequisite in JUDGED}
    if shipped != declared:
        raise HarnessFault(
            'the judge packet and the rubric disagree on the judged set: '
            f'packet_only={sorted(shipped - declared)} rubric_only={sorted(declared - shipped)}'
        )
    return [
        {
            'criterion': item_id,
            'judgment': PACKET['judgments'][item_id],
            'prerequisite': prerequisite,
            'weight': weight,
            'model': PACKET['model'],
            'temperature': PACKET['temperature'],
            'score_range': PACKET['score_range'],
        }
        for item_id, weight, prerequisite in JUDGED
    ]


def main() -> int:
    try:
        requests = build_requests()
    except HarnessFault as fault:
        print(json.dumps({'harness_failure': True, 'reason': str(fault)}), file=sys.stderr)
        return 3
    for request in requests:
        print(json.dumps(request, sort_keys=True))
    return 0


# In-flow judge (the S5-live caller, production path). The request-emitting entry point above
# is retained for offline inspection; this model-caller is what test.sh runs so ONE verifier
# pass yields the complete compiled+judge reward. Single-vendor OpenAI-compatible judge: the
# model comes from RAVEN_JUDGE_MODEL or packet.json; OPENAI_BASE_URL reaches a local
# OpenAI-compatible bridge (the QC validation path) or the public endpoint. A missing/invalid
# credential raises RuntimeError so the trial fails loud rather than folding a default verdict.
def _call_judge_model(prompt: str) -> str:
    import os
    import urllib.error
    import urllib.request

    model = (os.environ.get('RAVEN_JUDGE_MODEL', '').strip()
             or PACKET.get('model', '')
             or 'openai/gpt-6.1-sol').split('/')[-1]
    api_key = os.environ.get('OPENAI_API_KEY', '').strip()
    base = os.environ.get('OPENAI_BASE_URL', '').strip() or 'https://api.openai.com/v1'
    base = base.rstrip('/')
    if not base.endswith('/v1'):
        base = base + '/v1'
    url = base + '/chat/completions'

    # Force a single bare JSON object; the subtractive reducer regex-parses "score" from the text.
    # A system instruction is used (not response_format=json_object, which some bridges reject).
    messages = [
        {'role': 'system', 'content': (
            'You are a strict grader. Return nothing but a single JSON object '
            '{"score": <float 0..1>, "justification": "<one sentence>"}. No prose, no code fence.'
        )},
        {'role': 'user', 'content': prompt},
    ]

    def _post(payload: dict) -> dict:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode('utf-8'), method='POST',
            headers={'content-type': 'application/json',
                     'authorization': f'Bearer {api_key}'},
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode('utf-8'))

    # max_tokens 4000: a reasoning model can spend ~2000 on hidden reasoning and still owe the JSON.
    try:
        try:
            payload = _post({'model': model, 'messages': messages,
                             'temperature': PACKET.get('temperature', 0), 'max_tokens': 4000})
        except urllib.error.HTTPError as exc:
            # Retry without the optional fields a stricter endpoint may 400 on; any other status
            # (401/404/5xx) is a real failure and must raise so the trial fails loud.
            if exc.code != 400:
                detail = exc.read().decode('utf-8', 'replace')[:300] if hasattr(exc, 'read') else ''
                raise RuntimeError(f'judge unreachable: HTTP {exc.code}: {detail}') from exc
            payload = _post({'model': model, 'messages': messages})
    except urllib.error.URLError as exc:
        raise RuntimeError(f'judge unreachable: {exc}') from exc

    choices = payload.get('choices') or []
    if not choices:
        raise RuntimeError(f'judge returned no choices: {str(payload)[:300]}')
    content = choices[0].get('message', {}).get('content', '')
    if isinstance(content, list):
        content = ''.join(
            part.get('text', '') for part in content if isinstance(part, dict)
        )
    return content or ''


def run_live(workspace: str, out_path: str) -> int:
    import os
    import re

    prompt_contract = (_HERE / 'prompt.md').read_text(encoding='utf-8')
    ws = Path(workspace)
    eventlog = json.loads((ws / 'eventlog.json').read_text(encoding='utf-8'))
    events = eventlog.get('event_log', {}).get('past_events', [])
    writes, reads, written_paths = [], [], []
    for e in events:
        act = e.get('action') if isinstance(e.get('action'), dict) else None
        if act is None:
            for v in e.values():
                if isinstance(v, dict) and 'function_name' in v:
                    act = v
                    break
        if not act:
            continue
        fn = (act.get('function_name') or '')
        args = {k: v for k, v in (act.get('args') or {}).items() if k != 'tool_metadata'}
        line = f"{act.get('app_name')}.{fn} args={json.dumps(args)[:2000]}"
        hint = ('add', 'send', 'order', 'checkout', 'delete', 'reply', 'cancel', 'create', 'move', 'edit')
        # A Files write is only observable as open(mode=w/a/x): the written bytes never enter the
        # eventlog, so record the path to surface its body as prose below (else a quality judge
        # sees only "opened for write" and cannot assess the artifact it is grading).
        is_file_write = act.get('app_name') == 'Files' and (
            str(args.get('mode') or '').startswith(('w', 'a', 'x'))
            or any(h in fn.lower() for h in ('write', 'upload', 'put', 'touch'))
        )
        (writes if (is_file_write or any(h in fn.lower() for h in hint)) else reads).append(line)
        if is_file_write and isinstance(args.get('path'), str) and args['path'] not in written_paths:
            written_paths.append(args['path'])

    state_text, written_docs = '', ''
    state_path = ws / 'appstate.json'
    if state_path.exists():
        st = json.loads(state_path.read_text(encoding='utf-8'))
        keep = {k: st.get(k) for k in ('Calendar', 'Emails', 'CabApp', 'Messages', 'ShoppingApp', 'Files') if k in st}
        state_text = json.dumps(keep, default=str)[:28000]
        # ONLY paths this episode wrote. Seeded universe docs are read via Files.cat and never
        # listed here, so this surfaces the agent's own artifacts and leaks no answer key.
        contents = ((st.get('Files') or {}).get('contents') or {})
        blocks = [f'--- {p} ---\n{contents[p][:6000]}'
                  for p in written_paths
                  if isinstance(contents.get(p), str) and contents[p].strip()]
        written_docs = '\n\n'.join(blocks)[:20000]

    evidence = ('WRITES:\n' + '\n'.join(writes)
                + '\n\nREADS(sample):\n' + '\n'.join(reads[:120])
                # Before FINAL STATE so the 70000 cap truncates the JSON blob, not the prose.
                + ('\n\nDOCUMENTS THE AGENT WROTE THIS EPISODE (verbatim):\n' + written_docs if written_docs else '')
                + ('\n\nFINAL STATE:\n' + state_text if state_text else ''))[:70000]

    descriptions = {}
    for line in prompt_contract.splitlines():
        m = re.match(r'- `(j_[a-z_]+)`.*?\): (.*)', line)
        if m:
            descriptions[m.group(1)] = m.group(2)

    verdicts: dict[str, dict] = {}
    for request in build_requests():
        cid = request['criterion']
        prompt = (
            prompt_contract
            + f"\n\n=== NOW GRADE: {cid} ===\n{descriptions.get(cid, cid)}\n\n"
            + f"EVIDENCE:\n{evidence}\n\n"
            + 'Return ONLY {"score": <float 0..1>, "justification": "<one sentence>"}.'
        )
        out = _call_judge_model(prompt)
        sm = re.search(r'"score"\s*:\s*([0-9]*\.?[0-9]+)', out)
        if not sm:
            print(json.dumps({'harness_failure': True, 'reason': f'{cid}: no score in judge output'}), file=sys.stderr)
            return 3
        verdicts[cid] = {'score': float(sm.group(1))}
        jm = re.search(r'"justification"\s*:\s*"([^"]*)"', out)
        print(f"  {cid:24s} score={verdicts[cid]['score']:.2f}  {(jm.group(1) if jm else '')[:80]}", file=sys.stderr)
    Path(out_path).write_text(json.dumps(verdicts, indent=2), encoding='utf-8')
    print(f"wrote {len(verdicts)} verdicts to {out_path}", file=sys.stderr)
    return 0


if __name__ == '__main__':
    import os
    if os.environ.get('RAVEN_JUDGE_LIVE_OUT'):
        raise SystemExit(run_live(os.environ.get('RAVEN_VERIFIER_WORKSPACE', '/logs/artifacts'),
                                  os.environ['RAVEN_JUDGE_LIVE_OUT']))
    raise SystemExit(main())
