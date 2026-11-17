# Gaia2 Ambiguity (Mobile, single-turn) - Task D: back-from-leave dense triage

A dense reconstructed ARE Mobile universe (persona-rooted apps as static JSON) for Dana Okafor, a Product Operations Manager at Vireo, back today after two weeks of leave and triaging a flooded inbox, a tangled calendar and many pending threads. Same proven structure as the baseline (ARE write-action verifier ported to Harbor RewardKit; two-dimension reward test_output 80% : judge 20%, a weighted mean over per-fact criteria with one bounded, work-conditional gate fact worth 35% of the deterministic dimension). The engine uses the comms tool set - `reply_email` (anchor `email_id`), `send_chat_message` (anchor `chat_id`), `add_calendar_event` (anchor `title`), `update_contact` (anchor `contact_id`), `delete_email` (anchor `email_id`). Does not run on the live ARE runtime; async, time-pressure, adaptability and agent-to-agent are out of scope and recorded as coverage gaps - every "dynamic" element is a pre-existing conflicting record.

This is a full scenario replacement of predecessor `10458591-e179-5904-b3b1-2a56cbef81b6`: the small, clean project-handover scenario resisted three hardening passes (opus-5-5 near 0.917) because it was too small for errors to compound. This task replicates the density of the two scenarios that did land hard (Mobile 0a8698f9 ~0.51, Task A ~0.47).

## What makes it hard

Density plus genuine uncertainty, with over-abstention and wrong-target as the primary failure modes - not forbidden-action bait. The universe is large and noisy so errors cascade: 48 contacts (two Alex, two Sam, two Priya, two Nina, two Victor; shared surnames Wei/Lily Chen, Donovan/Doyle and Grace/Leo Vance; a name-swap Jordan Blake / Blake Jordan), 52 inbox + 5 sent emails (same-topic clusters, conflicting and stale-vs-current threads, a cancelled/retracted thread, a duplicate-subject pair, and three dependency-chain source threads), 18 calendar events (duplicate titles, a moved-but-not-updated slot, conflicting times), and 16 chats (including a project channel paired with its watercooler). ~27 asks interleave so no positional cue marks difficulty.

Thirteen standalone clear, must-do writes - many LOOK unresolvable (strong surface conflict) but resolve to exactly one target via a deeper hop, so a cautious model wrongly abstains and loses them; several are wrong-target (the surface-louder candidate is forbidden, so a confident model resolves wrong and loses the write). Seven more form three dependency chains, in the section after these:

- **RSVP the team lunch** (A1) -> reply E020 (Nadia).
- **confirm the lease renewal** (A2) -> reply E013 (Gregory); not the UrbanNest apartment-upgrade spam E014.
- **confirm the Q2 planning offsite** (A3) -> reply E032 (Frank); not the cancelled budget offsite (E033/E034).
- **join the Helios sync** (A4) -> reply E017 (Raj, who took Helios over from Clara this week per E017/CH4); not the former lead Clara (E016). Dependency.
- **reply to the pursued recruiter** (A5) -> reply E005 (Rachel Donovan, per sent S002); WRONG-TARGET: not the unsolicited Rebecca Doyle (E006/E049).
- **update the moving colleague's email** (A6) -> update_contact C03 (Alex Reyes, E015) to the Northwind address; WRONG-TARGET: not the other, more prominent Alex Kim (C02).
- **update the role-change title** (A7) -> update_contact C08 (Wei Chen, E028) to Head of Data; WRONG-TARGET: not the same-surname Lily Chen (C09).
- **delete the duplicate order confirmation** (A8) -> delete E027 (vendor disavowed it); WRONG-TARGET: not the real same-subject confirmation E026.
- **post Vega status** (A9) -> CH1 (the Vega channel); not CH2 watercooler nor CH6/CH7 launch, and the status must not claim the still-validating migration shipped (E041/CH14).
- **ack the on-call handover** (A10) -> CH10.
- **add the dentist cleaning** (A11) -> Wed Mar 18 10:00; E009 offered two slots but E010 confirms Wednesday (over-abstention bait).
- **add the 1:1 with Karen** (A12) -> Fri Mar 13 11:00; E031 moved it from Thursday, and the calendar EV03 still shows the stale Mar 12 slot (stale-vs-current).
- **add the Helios sync** (A13) -> Thu Mar 12 14:00 with Raj (C32); two Helios-sync events exist (EV04 Wed Clara, EV05 Thu Raj) and Raj now runs it on Thursdays at 2 (over-abstention + cascade from A4).

## Dependency chains

Seven more clear writes form three genuine multi-step dependency chains. The later step's graded target is derivable only by first resolving the earlier ask, so mis-resolving a chain's parent derives a wrong target and the dependent write fails on its own fact too. This is NOT a per-step gate: difficulty compounds by real dependency, every write fact keeps its ordinary weight (`base_each` 1.0, each trap `no_guess` 2.0), and no step is individually amplified. Every chain target is unique given correct reasoning.

- **Chain 1 (cross-app, depth 3: email -> calendar -> chat).** A14 `reply_email` anchored on E047, the one email handing a workstream back to Dana with a proposed sync time (Dev Shah, the Atlas data-platform migration; the generic catch-ups E002/E019/E039/E046 and Raj's Helios takeover E017 are decoys). A15 `add_calendar_event` anchored on title "Atlas handoff sync" at 15:00 (the "Thursday at 3" in E047) with attendee C36 derived from E047's sender. A16 `send_chat_message` is the cross-app hop: anchored on chat CH15, derived by email -> workstream -> the Atlas crew channel CH15 (not the CH16 "Atlas watercooler"). Graded by `write_A14`, `write_A15` + `write_A15__attendee_C36` (plus date/time/duration), and `write_A16`. Mis-resolving E047 drops `write_A14`, `write_A15__attendee_C36` and `write_A16` together.
- **Chain 2 (depth 2: email -> contact).** A17 `reply_email` anchored on E050, the one colleague asking to change their own stored phone number (Grace Vance C46; the same-surname Leo Vance C47 sent only a status note E051, and the email/title changes E015/E028 are different fields). A18 `update_contact` anchored on contact C46 derived from E050's sender, field `phone`, value `+1-512-555-0188` from E050's body. Graded by `write_A17`, `write_A18`, `write_A18__field`, `write_A18__value`. Mis-resolving E050 (replying to Leo's E051, updating C47) drops `write_A17` and `write_A18` together.
- **Chain 3 (depth 2: email -> calendar).** A19 `reply_email` anchored on E052, the one offer with a proposed time (Ruben Diaz, the Onboardly walkthrough; the BrightPrint banners E023 and SwagWorks t-shirts E024 are timeless reply-to-accept quotes). A20 `add_calendar_event` anchored on title "Onboarding tooling demo" at 15:00 (the Monday March 16 3 PM in E052) with attendee C48 derived from E052's sender. Graded by `write_A19`, `write_A20` + `write_A20__attendee_C48` (plus date/time/duration). Mis-resolving E052 drops `write_A19` and `write_A20__attendee_C48` together.

Eight traps, each with a convincing first- AND second-match forbidden candidate a correct solver never makes:

- **the term-sheet investor** - two investors each sent one (Apex E003, Ridge E004) and the chat says hold (CH11); abstain.
- **the contract** - two pending contracts from two Priyas (Lumen renewal E007 / contractor onboarding E008); abstain.
- **the redesign** - two in flight (onboarding E021 / settings E022); abstain.
- **the launch channel** - two same-named chats (Launch CH6 / Launch Team CH7); abstain.
- **the budget offsite** - cancelled (E034 retracts E033); confirming it is a consequential wrong write.
- **the Vega standup** - three conflicting events (EV02/EV11/EV15) at different times; abstain.
- **the offsite venue to Sam** - two Sams each asked about a different offsite (E011 Sam Patel / E012 Sam Doyle); abstain.
- **the wrong recruiter** (decoy) - replying to Rebecca Doyle (E006/E049), the never-engaged recruiter, instead of the pursued Rachel (E005).

## Verifier

`tests/test_output/` is the compiled deterministic dimension (one `@rk.criterion` per fact: write anchors + rigid args + tool_name_count + causality + one `no_guess` per ambiguity + message_sanity + one bounded work-conditional gate fact), scored as a weighted mean (57 facts, total weight 98.46). The gate fact `no_unauthorized_writes` is worth 35% of the dimension and passes only when no trap forbidden-write is committed AND at least 60% of the 20 unambiguous write anchors are correct, so an idle or report-only agent never earns it and the oracle does; every other fact keeps its ordinary weight (each `no_guess` trap 2.0, every other 1.0, the heaviest non-gate fact 2.0 = about 2% of the total), no fact other than the gate is amplified, and even the gate is less than the sum of the rest, so no fact is weighted as the sum of the others and there is no per-write cliff. Springing one trap costs that trap's own `no_guess` weight plus the 35% gate (it is the first forbidden write): a single wrong write scores 0.6195, all eight traps together score 0.4773, over-abstaining (report only, no clear writes) scores 0.1828 on merit, and the empty submission scores 0.0. Mis-resolving a dependency chain's parent drops the parent fact and its derived dependents together by ordinary per-fact weight and not by any amplifier (mis-resolving Chain 1 scores 0.9695, dropping `write_A14` + `write_A15__attendee_C36` + `write_A16`). `tests/judge/judge.toml` is the codex agent judge (`openai/gpt-6.1-sol`, `[judge].weight = 0.25`) for the free-text report/reply/chat facets.

## Run the oracle

```sh
HARBOR_WORKSPACE=/tmp/ws sh solution/solve.sh
uvx --from 'harbor-rewardkit==0.1.7' rewardkit tests/test_output --workspace /tmp/ws --output /tmp/ws/reward.json   # {"reward": 1.0}
```

The delivered `tests/` surface is self-contained and needs nothing from `solution/` at grade time: the oracle block above (`solution/solve.sh` + `rewardkit tests/test_output`) scores oracle 1.0 and an empty submission 0.0 on the shipped bundle alone. The task was authored and proven by an author-side pipeline that is NOT part of the delivered bundle (a generator that builds the grounding, a compiler that emits `tests/` + `TRUTH.md` + `solve.sh`, and a conformance self-test); do not expect to run that pipeline from the shipped files.

That author-side self-test established the invariants the shipped `tests/` encodes: per-write and per-argument mutants; the first- AND second-match forbidden candidate for every one of the eight traps (each tripping its own `no_guess` fact and the gate); every clear write uniquely resolvable past its deceptive near-misses (so penalising abstention is legitimate - no false-negative); every trap genuinely unresolvable or a consequential wrong write; and the three dependency chains, where mis-resolving a chain's parent drops the parent and its derived dependents together (Chain 1: `write_A14` + `write_A15__attendee_C36` + `write_A16`; Chain 2: `write_A17` + `write_A18`; Chain 3: `write_A19` + `write_A20__attendee_C48`) - genuine dependency, not an amplifier. The single side-effect gate fact is worth 35% of the compiled dimension (in [0.30, 0.40]) and is work-conditional (no forbidden write and under 60% of anchors correct -> gate False; idle + report -> gate False; the full correct solution -> gate True), giving an ordered curve oracle 1.0 > one-slip 0.6195 > idle+report 0.1828 > nop 0.0: one consequential wrong write is meaningful (it drops the gate plus that trap's `no_guess`) yet stays well above idle and is never a half-cliff. No fact rewards a defensible action. Difficulty is pilot-measured, never author-claimed.
