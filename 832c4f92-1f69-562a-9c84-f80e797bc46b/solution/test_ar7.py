#!/usr/bin/env python3
"""Author-side conformance probe for the back-from-leave dense triage task (GAIA2 Mobile).

Proves the legitimacy the brief demands: oracle 1.0 / empty 0.0; the gateless weight scheme (plain
weighted mean, no side-effect gate); per-write anchor and per-argument mutants; each of the eight
traps tripping its no_guess fact on BOTH a first- and second-match forbidden candidate;
universe coherence; every clear write uniquely resolvable through a deeper hop past its deceptive
near-misses (so penalising abstention is legitimate - no false-negative); and every trap genuinely
unresolvable or a consequential wrong write a correct solver never makes. test_oracle_trips_no_trap
confirms the full correct solution springs nothing. Judge dimension checked structurally.
"""
from __future__ import annotations
import datetime, json, pathlib, sys, tempfile, tomllib

HERE = pathlib.Path(__file__).resolve().parent; BUNDLE = HERE.parent
ENV = BUNDLE / "environment"; TO = BUNDLE / "tests" / "test_output"
sys.path.insert(0, str(TO)); sys.dont_write_bytecode = True
import are_verifier  # noqa: E402
ORACLE = json.loads((TO / "oracle.json").read_text())
_GROUNDING_PATH = HERE / "grounding.yaml"
if not _GROUNDING_PATH.exists():
    print("ok: author-side self-test skipped (grounding.yaml not present in this delivery copy)")
    raise SystemExit(0)
GROUNDING = json.loads(_GROUNDING_PATH.read_text())
WEIGHTS = ORACLE["compiled_weights"]
UNAMB = [a for a in ORACLE["oracle_actions"] if a["role"] == "unambiguous"]; GATE = "no_unauthorized_writes"
SUB = [{"tool": a["tool"], "args": a["args"]} for a in ORACLE["oracle_actions"]]
def _load(n): return json.loads((ENV / n).read_text())
CONTACTS = _load("contacts.json"); BYID = {c["id"]: c for c in CONTACTS}; EMAIL2ID = {c["email"]: c["id"] for c in CONTACTS}
INBOX = _load("emails/inbox.json"); SENT = _load("emails/sent.json"); CAL = _load("calendar.json"); PERSONA = _load("persona.json")["handle"]
CHATS = {}
for _p in sorted((ENV / "chats").glob("*.json")):
    _d = json.loads(_p.read_text()); CHATS[_d["chat_id"]] = _d
def _grade(acts):
    with tempfile.TemporaryDirectory() as t:
        w = pathlib.Path(t); (w / "actions.json").write_text(json.dumps(acts)); return are_verifier.grade(w, ORACLE)
def _oarg(aid, k): return next(a["args"][k] for a in UNAMB if a["id"] == aid)
def _em(eid): return next(e for e in INBOX if e["email_id"] == eid)
def _fname(cid): return BYID[cid]["name"].split()[0]
def _sname(cid): return BYID[cid]["name"].split()[-1]

def test_oracle_full():
    r = _grade(SUB); assert r["reward"] == 1.0, r; assert all(f["pass"] for f in r["facts"].values())
def test_empty_zero():
    r = _grade([]); assert r["reward"] == 0.0 and not any(f["pass"] for f in r["facts"].values())
def test_weights_scheme_gate():
    cw = GROUNDING["compiled_weighting"]; ng_each, base_each = cw["no_guess_each"], cw["base_each"]
    assert ng_each > base_each > 0 and ng_each <= 3 * base_each  # small constant multiple, not a cliff
    # one bounded, work-conditional gate fact EXISTS and is worth ~35% of the deterministic dimension
    assert GATE in WEIGHTS
    total = sum(WEIGHTS.values())
    assert 0.30 <= WEIGHTS[GATE] / total <= 0.40
    assert abs(WEIGHTS[GATE] / total - cw["gate_fraction"]) < 1e-6
    # every non-gate fact keeps its ordinary weight; none is amplified or weighted as sum-of-others
    ng = ["no_guess_" + a["id"] for a in ORACLE["ambiguities"]]
    base = [k for k in WEIGHTS if k not in ng and k != GATE]
    assert len(ng) == len(ORACLE["ambiguities"]) >= 8
    for k in ng: assert WEIGHTS[k] == ng_each
    for k in base: assert WEIGHTS[k] == base_each
    nongate = [v for k, v in WEIGHTS.items() if k != GATE]
    assert max(nongate) == ng_each                        # no amplified non-gate fact
    assert max(nongate) < 0.15 * total                    # no non-gate fact is a large fraction
    assert WEIGHTS[GATE] < total - WEIGHTS[GATE]           # even the gate is less than the sum of the rest
    # work-conditional: no forbidden write but < 60% of the 20 anchors correct -> gate False
    writes = [a for a in SUB if a["tool"] != "send_message_to_user"]
    report = [a for a in SUB if a["tool"] == "send_message_to_user"]
    assert len(writes) == 20
    assert _grade(writes[:10] + report)["facts"][GATE]["pass"] is False   # 10/20 = 50%
    # >= 60% anchors and no forbidden -> gate True (boundary at 12/20 = 60%)
    assert _grade(writes[:12] + report)["facts"][GATE]["pass"] is True
    # idle + report only -> gate False (never earned by a report-only agent)
    assert _grade(report)["facts"][GATE]["pass"] is False
    # the oracle earns the gate (no forbidden, all anchors) and empty never does
    assert _grade(SUB)["facts"][GATE]["pass"] is True
    assert _grade([])["facts"][GATE]["pass"] is False
def test_every_fact_registered():
    assert set(_grade(SUB)["facts"]) == set(WEIGHTS) == set(_grade([])["facts"])
def test_per_write_anchor_mutant():
    worst = 0.0
    for w in UNAMB:
        anchor = are_verifier.ANCHOR[w["tool"]]; mut = []
        for a in SUB:
            if a["tool"] == w["tool"] and a["args"] == w["args"]:
                bad = dict(a["args"]); bad[anchor] = "MUTANT"; mut.append({"tool": a["tool"], "args": bad})
            else: mut.append(a)
        r = _grade(mut); assert r["facts"]["write_" + w["id"]]["pass"] is False, w["id"]; worst = max(worst, r["reward"])
    return worst
def test_per_argument_mutant():
    for aid, arg in (("A6", "field"), ("A6", "value"), ("A7", "field"), ("A7", "value"),
                     ("A11", "date"), ("A11", "time"), ("A11", "duration_min"),
                     ("A12", "date"), ("A12", "time"), ("A13", "date")):
        w = next(a for a in UNAMB if a["id"] == aid); mut = []
        for a in SUB:
            if a["tool"] == w["tool"] and a["args"] == w["args"]:
                bad = dict(a["args"]); bad[arg] = "MUT" if not isinstance(bad[arg], int) else 999; mut.append({"tool": a["tool"], "args": bad})
            else: mut.append(a)
        r = _grade(mut)
        assert r["facts"]["write_" + aid]["pass"] is True and r["facts"]["write_" + aid + "__" + arg]["pass"] is False, (aid, arg)
def test_wrong_attendee():
    mut = [({"tool": a["tool"], "args": {**a["args"], "attendees": ["C99"]}} if a["args"].get("title") == "1:1 with Karen" else a) for a in SUB]
    assert _grade(mut)["facts"]["write_A12__attendee_C01"]["pass"] is False

_body = {"body": "ok"}; _text = {"text": "ok"}
def _reply(eid): return {"tool": "reply_email", "args": {"email_id": eid, **_body}}
def _chat(cid): return {"tool": "send_chat_message", "args": {"chat_id": cid, **_text}}
def _vega(t): return {"tool": "add_calendar_event", "args": {"title": "Vega standup", "date": "2026-03-10", "time": t, "duration_min": 30, "attendees": []}}
FIRST = {
 "AMB_TERMSHEETS": _reply("E003"),
 "AMB_CONTRACT": _reply("E007"),
 "AMB_REDESIGN": _reply("E021"),
 "AMB_LAUNCH_CHAT": _chat("CH6"),
 "AMB_BUDGET_CANCELLED": _reply("E034"),
 "AMB_VEGA_STANDUP": _vega("10:00"),
 "AMB_OFFSITE_VENUE": _reply("E011"),
 "AMB_WRONG_RECRUITER": _reply("E006"),
}
SECOND = {
 "AMB_TERMSHEETS": _reply("E004"),
 "AMB_CONTRACT": _reply("E008"),
 "AMB_REDESIGN": _reply("E022"),
 "AMB_LAUNCH_CHAT": _chat("CH7"),
 "AMB_BUDGET_CANCELLED": _reply("E033"),
 "AMB_VEGA_STANDUP": _vega("16:00"),
 "AMB_OFFSITE_VENUE": _reply("E012"),
 "AMB_WRONG_RECRUITER": _reply("E049"),
}
def test_first_match_traps_trip_no_guess():
    assert set(FIRST) == {a["id"] for a in ORACLE["ambiguities"]}
    for amb, guess in FIRST.items():
        r = _grade(SUB + [guess])
        assert r["facts"]["no_guess_" + amb]["pass"] is False, amb
        assert r["facts"][GATE]["pass"] is False, amb   # a forbidden write fails the gate too
        assert r["reward"] < 1.0, (amb, r["reward"])
def test_second_match_traps_trip_no_guess():
    assert set(SECOND) == {a["id"] for a in ORACLE["ambiguities"]}
    for amb, guess in SECOND.items():
        r = _grade(SUB + [guess])
        assert r["facts"]["no_guess_" + amb]["pass"] is False, amb
        assert r["facts"][GATE]["pass"] is False, amb
def test_oracle_trips_no_trap():
    r = _grade(SUB)
    for a in ORACLE["ambiguities"]:
        assert r["facts"]["no_guess_" + a["id"]]["pass"] is True, a["id"]
    assert r["facts"][GATE]["pass"] is True   # oracle commits no forbidden write and earns the gate

CHAIN_FACTS = ["write_A14", "write_A15__attendee_C36", "write_A16",
               "write_A17", "write_A18", "write_A18__value",
               "write_A19", "write_A20__attendee_C48"]
def test_dependency_chains():
    assert len(UNAMB) == 20   # 13 standalone + 7 chained writes (A14..A20); report A21 is not unambiguous
    # chain targets are uniquely resolvable only via each chain's derivation
    assert EMAIL2ID[_em("E047")["sender"]] == "C36" and CHATS["CH15"]["title"] == "Atlas" and CHATS["CH16"]["title"] == "Atlas watercooler"
    assert EMAIL2ID[_em("E050")["sender"]] == "C46" and EMAIL2ID[_em("E051")["sender"]] == "C47" and _sname("C46") == _sname("C47") == "Vance"
    assert EMAIL2ID[_em("E052")["sender"]] == "C48"
    assert "+1-512-555-0188" in _em("E050")["body"] and _oarg("A18", "value") == "+1-512-555-0188"
    assert _oarg("A15", "time") == "15:00" and "thursday at 3" in _em("E047")["body"].lower()
    assert _oarg("A20", "time") == "15:00" and "march 16 at 3" in _em("E052")["body"].lower()
    # (i) the oracle earns every chained fact (parents AND derived dependents)
    r = _grade(SUB)
    for k in CHAIN_FACTS:
        assert r["facts"][k]["pass"] is True, k
    # (ii) PROPAGATION chain 1: mis-resolve the parent (reply E002 not E047) and derive the dependents
    # from it (attendee C02 not C36, chat CH1 not CH15). Parent AND both dependents drop.
    misA = []
    for a in SUB:
        if a["tool"] == "reply_email" and a["args"].get("email_id") == "E047":
            misA.append({"tool": "reply_email", "args": {**a["args"], "email_id": "E002"}})
        elif a["tool"] == "add_calendar_event" and a["args"].get("title") == "Atlas handoff sync":
            misA.append({"tool": "add_calendar_event", "args": {**a["args"], "attendees": ["C02"]}})
        elif a["tool"] == "send_chat_message" and a["args"].get("chat_id") == "CH15":
            misA.append({"tool": "send_chat_message", "args": {**a["args"], "chat_id": "CH1"}})
        else:
            misA.append(a)
    ra = _grade(misA)
    assert ra["facts"]["write_A14"]["pass"] is False
    assert ra["facts"]["write_A15__attendee_C36"]["pass"] is False
    assert ra["facts"]["write_A16"]["pass"] is False
    # (ii) PROPAGATION chain 2: mis-resolve the parent (reply E051 not E050) and update the wrong Vance
    # (C47 not C46). Parent AND dependent drop.
    misB = []
    for a in SUB:
        if a["tool"] == "reply_email" and a["args"].get("email_id") == "E050":
            misB.append({"tool": "reply_email", "args": {**a["args"], "email_id": "E051"}})
        elif a["tool"] == "update_contact" and a["args"].get("contact_id") == "C46":
            misB.append({"tool": "update_contact", "args": {**a["args"], "contact_id": "C47"}})
        else:
            misB.append(a)
    rb = _grade(misB)
    assert rb["facts"]["write_A17"]["pass"] is False
    assert rb["facts"]["write_A18"]["pass"] is False
    # (ii) PROPAGATION chain 3: mis-resolve the parent (reply E023 not E052) and derive the attendee
    # from it (C19 not C48). Parent AND dependent drop.
    misC = []
    for a in SUB:
        if a["tool"] == "reply_email" and a["args"].get("email_id") == "E052":
            misC.append({"tool": "reply_email", "args": {**a["args"], "email_id": "E023"}})
        elif a["tool"] == "add_calendar_event" and a["args"].get("title") == "Onboarding tooling demo":
            misC.append({"tool": "add_calendar_event", "args": {**a["args"], "attendees": ["C19"]}})
        else:
            misC.append(a)
    rc = _grade(misC)
    assert rc["facts"]["write_A19"]["pass"] is False
    assert rc["facts"]["write_A20__attendee_C48"]["pass"] is False
    return r["reward"], ra["reward"]
def test_prechecks():
    r = _grade(SUB)
    assert r["facts"]["tool_name_count"]["pass"] and r["facts"]["causality"]["pass"] and r["facts"]["message_sanity"]["pass"]
    assert _grade(SUB + [{"tool": "delete_email", "args": {"email_id": "E099"}}])["facts"]["tool_name_count"]["pass"] is False

def test_universe_coherent():
    assert len(CONTACTS) >= 40 and len(INBOX) >= 40 and len(CAL) >= 15 and len(CHATS) >= 12
    assert len(EMAIL2ID) == len(CONTACTS)   # no duplicate contact emails
    for v in CAL:
        assert v["organizer"] == PERSONA or v["organizer"] in BYID, v
        assert set(v["attendees"]) <= (set(BYID) | {PERSONA}), v
    for cid, d in CHATS.items():
        for p in d["participants"]: assert p == PERSONA or p in BYID, (cid, p)
    emails = {e["email_id"] for e in INBOX}; chats = set(CHATS)
    for a in UNAMB:
        if a["tool"] == "reply_email": assert a["args"]["email_id"] in emails, a
        if a["tool"] == "send_chat_message": assert a["args"]["chat_id"] in chats, a
        if a["tool"] == "update_contact": assert a["args"]["contact_id"] in BYID, a
        if a["tool"] == "delete_email": assert a["args"]["email_id"] in emails, a
    for amb in ORACLE["ambiguities"]:
        for rule in amb["forbidden_writes"]:
            if rule["field"] == "email_id":
                for v in rule["in"]: assert v in emails, (amb["id"], v)
            if rule["field"] == "chat_id":
                for v in rule["in"]: assert v in chats, (amb["id"], v)

def test_clear_writes_resolve_to_one_target():
    # A1 lunch RSVP -> Nadia E020
    assert _oarg("A1", "email_id") == "E020" and _em("E020")["sender"] == "nadia.rahman@vireo.example"
    # A2 lease renewal -> Gregory E013, not the UrbanNest upgrade spam E014
    assert _oarg("A2", "email_id") == "E013" and _em("E013")["sender"] == "gregory.tan@gmail.example"
    assert _em("E014")["sender"] != "gregory.tan@gmail.example" and "renew" not in _em("E014")["body"].lower()
    # A3 Q2 planning offsite -> Frank E032; budget offsite (E033) was cancelled by E034
    assert _oarg("A3", "email_id") == "E032" and "q2 planning" in _em("E032")["subject"].lower()
    assert "cancelled" in _em("E034")["body"].lower()
    # A4 Helios -> Raj E017 (took over from Clara), dependency hop
    assert _oarg("A4", "email_id") == "E017" and _em("E017")["sender"] == "raj.menon@vireo.example"
    assert "taken over" in _em("E017")["body"].lower() or "taken over" in _em("E017")["subject"].lower()
    assert _em("E016")["sender"] == "clara.nguyen@vireo.example"   # former lead, the near-miss
    # A5 recruiter -> Rachel E005 (pursued per sent S002), not Rebecca E006
    assert _oarg("A5", "email_id") == "E005" and _em("E005")["sender"] == "rachel.donovan@peakline.example"
    s002 = next(s for s in SENT if s["email_id"] == "S002"); assert s002["recipient"] == "rachel.donovan@peakline.example"
    assert _em("E006")["sender"] == "rebecca.doyle@northgate.example"
    # A6 update Alex Reyes C03 email, not the other Alex (Kim C02)
    assert _oarg("A6", "contact_id") == "C03" and _oarg("A6", "field") == "email" and _oarg("A6", "value") == "alex.reyes@northwind.example"
    assert _fname("C02") == _fname("C03") == "Alex" and "C02" != "C03"
    assert _em("E015")["sender"] == "alex.reyes@vireo.example" and "northwind" in _em("E015")["body"].lower()
    # A7 update Wei Chen C08 title, not same-surname Lily Chen C09
    assert _oarg("A7", "contact_id") == "C08" and _oarg("A7", "field") == "job" and _oarg("A7", "value") == "Head of Data"
    assert _sname("C08") == _sname("C09") == "Chen" and "C08" != "C09"
    assert _em("E028")["sender"] == "wei.chen@vireo.example"
    # A8 delete the duplicate order confirmation E027, not the real one E026 (same subject)
    assert _oarg("A8", "email_id") == "E027"
    assert "error" in _em("E027")["body"].lower() and "delete" in _em("E027")["body"].lower()
    assert "55120" in _em("E026")["subject"] and "55120" in _em("E027")["subject"] and _em("E026")["subject"] != _em("E027")["subject"]
    # A9 Vega status -> CH1 (the Vega channel), not CH2 watercooler nor CH6/CH7 launch
    assert _oarg("A9", "chat_id") == "CH1" and CHATS["CH1"]["title"] == "Vega"
    assert CHATS["CH2"]["title"] != "Vega" and "launch" not in CHATS["CH1"]["title"].lower()
    # A10 on-call ack -> CH10
    assert _oarg("A10", "chat_id") == "CH10" and "on-call" in CHATS["CH10"]["title"].lower()
    # A11 dentist Wed Mar 18 10:00 (E010 confirmed; E009 offered two) - over-abstention bait
    assert _oarg("A11", "title") == "Dentist cleaning" and _oarg("A11", "date") == "2026-03-18" and _oarg("A11", "time") == "10:00"
    assert "march 18" in _em("E010")["body"].lower() and "booked" in _em("E010")["subject"].lower()
    assert "march 17" in _em("E009")["body"].lower() and "march 18" in _em("E009")["body"].lower()   # E009 offers two
    # A12 1:1 with Karen Fri Mar 13 11:00 (E031 supersedes E030; stale calendar EV03 on Mar 12)
    assert _oarg("A12", "title") == "1:1 with Karen" and _oarg("A12", "date") == "2026-03-13" and _oarg("A12", "time") == "11:00" and _oarg("A12", "attendees") == ["C01"]
    assert "march 13" in _em("E031")["body"].lower() and "11:00" in _em("E031")["body"]
    ev03 = next(v for v in CAL if v["event_id"] == "EV03")
    assert ev03["title"] == "1:1 with Karen" and ev03["date"] == "2026-03-12"   # stale, moved-but-not-updated
    # A13 Helios sync Thu Mar 12 14:00 with Raj C32 (not stale Wed EV04 with Clara) - cascade from A4
    assert _oarg("A13", "title") == "Helios sync" and _oarg("A13", "date") == "2026-03-12" and _oarg("A13", "time") == "14:00" and _oarg("A13", "attendees") == ["C32"]
    assert datetime.date(2026, 3, 12).weekday() == 3   # Thursday, matching Raj's "Thursdays at 2"
    helios = [v for v in CAL if v["title"] == "Helios sync"]
    assert {v["event_id"] for v in helios} == {"EV04", "EV05"}
    assert next(v for v in helios if v["event_id"] == "EV04")["date"] == "2026-03-11"   # Wed, Clara, stale
    assert next(v for v in helios if v["event_id"] == "EV05")["organizer"] == "C32"     # Thu, Raj, current

def test_traps_genuine():
    # TERMSHEETS: two investors each sent one; chat says hold
    assert _em("E003")["sender"] == "victor.lang@apexvc.example" and _em("E004")["sender"] == "nina.rao@ridgecap.example"
    assert "term sheet" in _em("E003")["body"].lower() and "term sheet" in _em("E004")["body"].lower()
    assert any("term sheet" in m["text"].lower() for m in CHATS["CH11"]["messages"])
    # CONTRACT: two different contracts from two different Priyas
    assert _em("E007")["sender"] == "priya.shah@lumen.example" and _em("E008")["sender"] == "priya.nair@vireo.example"
    assert "contract" in _em("E007")["body"].lower() and "contract" in _em("E008")["body"].lower()
    assert _fname(EMAIL2ID["priya.shah@lumen.example"]) == _fname(EMAIL2ID["priya.nair@vireo.example"]) == "Priya"
    # REDESIGN: two separate redesigns in flight
    assert "redesign" in _em("E021")["body"].lower() and "redesign" in _em("E022")["body"].lower()
    assert _em("E021")["sender"] == "hana.suzuki@vireo.example" and _em("E022")["sender"] == "sam.doyle@vireo.example"
    # LAUNCH: two same-named launch chats, neither the Vega status channel
    assert "launch" in CHATS["CH6"]["title"].lower() and "launch" in CHATS["CH7"]["title"].lower() and CHATS["CH6"]["title"] != CHATS["CH7"]["title"]
    assert "CH1" not in ("CH6", "CH7")
    # BUDGET CANCELLED: E034 retracts E033; distinct from the real Q2 planning offsite E032
    assert "cancelled" in _em("E034")["body"].lower() and _em("E033")["sender"] == "frank.doyle@vireo.example"
    assert _em("E032")["email_id"] != _em("E033")["email_id"]
    # VEGA STANDUP: three conflicting events at different times, none the oracle's add
    vs = [v for v in CAL if v["title"] == "Vega standup"]
    assert len(vs) >= 3 and len({(v["date"], v["time"]) for v in vs}) >= 2
    assert all(_oarg(a, "title") != "Vega standup" for a in ("A11", "A12", "A13"))
    # OFFSITE VENUE: two Sams, two offsites
    assert _em("E011")["sender"] == "sam.patel@vireo.example" and _em("E012")["sender"] == "sam.doyle@vireo.example"
    assert _fname("C04") == _fname("C05") == "Sam"
    assert "venue" in _em("E011")["body"].lower() and "venue" in _em("E012")["body"].lower()
    # WRONG RECRUITER: Rebecca (E006/E049) is never-engaged; the pursued one is Rachel (E005, per S002)
    assert _em("E006")["sender"] == "rebecca.doyle@northgate.example" and _em("E049")["sender"] == "rebecca.doyle@northgate.example"
    assert _oarg("A5", "email_id") == "E005" and "E005" not in ("E006", "E049")
    assert next(s for s in SENT if s["email_id"] == "S002")["recipient"] == "rachel.donovan@peakline.example"

def test_judge_structural():
    cfg = tomllib.load(open(BUNDLE / "tests" / "judge" / "judge.toml", "rb"))
    assert cfg["judge"]["judge"] == "codex" and cfg["judge"]["weight"] == 0.25
    crit = cfg["criterion"]; assert len(crit) == len(GROUNDING["judge_criteria"]) >= 20
    assert abs(sum(c["weight"] for c in crit) - 1.0) < 1e-6

def test_score_curve():
    # Bounded 35% work-conditional gate: oracle full, nop zero, report-only low, one slip between them.
    oracle = _grade(SUB)["reward"]
    one = _grade(SUB + [FIRST["AMB_TERMSHEETS"]])["reward"]
    idle = _grade([a for a in SUB if a["tool"] == "send_message_to_user"])["reward"]
    nop = _grade([])["reward"]
    assert oracle == 1.0 and nop == 0.0
    assert idle < one < oracle          # report-only is lowest of the three; one-slip sits between idle and oracle
    assert idle < 0.30                  # idle + report only is genuinely low (no gate, no writes)
    assert (oracle - one) > 0.30        # one consequential wrong write drops at least the 35% gate
    return oracle, one, idle, nop

if __name__ == "__main__":
    for fn in [test_oracle_full, test_empty_zero, test_weights_scheme_gate, test_every_fact_registered,
               test_per_write_anchor_mutant, test_per_argument_mutant, test_wrong_attendee,
               test_first_match_traps_trip_no_guess, test_second_match_traps_trip_no_guess,
               test_oracle_trips_no_trap, test_prechecks, test_universe_coherent,
               test_clear_writes_resolve_to_one_target, test_traps_genuine, test_judge_structural]:
        fn()
    oc, chainA = test_dependency_chains()
    _oc, one, idle, nop = test_score_curve()
    print(f"score curve (gate): oracle={oc:.4f}  chain1-misresolved={chainA:.4f}  one-slip={one:.4f}  idle+report={idle:.4f}  nop={nop:.4f}")
    print("ok: Task D (dense triage) conformance checks passed (3 dependency chains + 35% work-conditional gate)")
