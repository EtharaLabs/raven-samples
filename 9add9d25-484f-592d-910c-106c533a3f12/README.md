# Gaia2 Ambiguity (Mobile, single-turn)

A reconstructed ARE Mobile universe with a single-turn, multi-part user request over a large, noisy universe that forces real cross-app reading. The request names no target by id: every part refers to people and things by role, relationship, or event, so the agent must join across apps to resolve each target, past two or three near-miss candidates. It must carry out the parts that resolve and report the parts that do not, without guessing. It reconstructs the Mobile environment as static structured data and does not run on the live ARE runtime (see the coverage gaps in the parent EDICT.md).

This hardening targets the failure mode in the paper (section 3.2): frontier models execute the first seemingly valid approach rather than recognizing the need for clarification, and they fail when correct targets must be inferred by reading across apps. The ambiguities are not telegraphed; they surface only after the agent cross-references apps. The clear parts are written so that shallow reading resolves them wrongly, and the ambiguous parts are interleaved among them so no positional cue marks which is which.

## Task

`instruction.md` asks, in plain natural language, for thirty-nine items: twenty-five clear asks that resolve to exactly one target each by a multi-app join (twenty-seven write actions in total, since clearing the offboarded vendor deletes three emails and the three dependency chains add seven more), plus fourteen that cannot be done as given. Every clear ask is hardened so the first-match surface candidate is a near-miss (same first name, overlapping role or employer, same-day or same-topic record) and the correct target is reached only by a further cross-app hop - e.g. the ledger-RFC author versus the engineer "taking over maintenance", the QA engineer's one-on-one versus the QA lead's, the analytics-review organizer versus the analytics-planning one, the board-meeting organizer's email versus the board-deck-review email. The fourteen unresolvable parts are each a different taxonomy kind, each with a tempting first-match trap:

- a message to the "startup catch-up group", ambiguous because two different chats share the exact title "Catch-up and Startup Updates" (CH1 and CH2), both startup groups mid-planning a meet-up (a third "College Catch-up" group is a near-duplicate title that is not a startup group);
- adding "the quarterly review" for "next Tuesday", impossible because there is no date anchor and no time (a past Q2 business review on a Tuesday is a tempting pattern to copy);
- replying to "Priya's email about the Q3 budget", which has no matching record: the two Priyas' emails are about reconciliation and Q4 budget, and the only Q3 budget email is from the finance lead;
- scheduling a call with "the investor who sent the term sheet", which has no unique referent because two investors each sent a term sheet, discoverable only by reading the inbox;
- messaging "the engineer currently on the backend on-call", unresolvable because two coworkers each claim the pager this week in conflicting records (one email and chat each);
- replying to "the vendor about our renewal" to confirm it, a contradictory request because the only renewal-referent email (Northwind) states they are *not* renewing and are closing the contract;
- deleting "the duplicate CloudSpan invoice", ambiguous because two inbox emails share the exact subject "CloudSpan invoice for July" and neither is marked original or superseding;
- updating "our platform lead's title to match the latest org chart", a conflicting-value case because two org-chart emails disagree on the new title;
- shifting "my sprint planning" to the afternoon, ambiguous because two events share the title "Sprint planning" and both are the user's;
- replying to "the product designer who emailed their latest work", with no unique referent because two product designers each emailed recent work;
- replying to "the landlord to confirm we're renewing the office lease", a contradictory request because the landlord's only office-lease email says they are selling the building and ending the lease;
- "RSVP yes to Sara's founder roundtable invite", a reference to a retracted record because a later email from Sara cancelled the roundtable;
- adding "my weekly planning at the usual time", a unit/format mismatch because the usual time is given as 4 PM in an email and 3 PM in a chat;
- replying to "the current payments-squad PM's handover note", conflicting/stale data because two coworkers each claim to be the current PM (one as interim).

The instruction directs the agent to finish the clear parts and report any ambiguity in its final message, and does not reveal which parts are ambiguous.

## Environment

`environment/` is a persona-rooted Mobile universe as structured data, cross-coherent (every sender, attendee, organizer, participant, and role reference resolves to exactly one contact or the persona):

- `persona.json` the user (Rohan Mehta);
- `contacts.json` the address book (67 contacts, with duplicate first names - including a second Rohan and a second Vivek - shared surnames, and overlapping roles as join hazards: a Design Manager beside the Design Lead, a Financial Controller and Finance Analyst beside the Finance Lead, an Operations Lead and Operations Analyst beside the Operations Manager, a QA Lead beside the QA Engineer, Product Designers beside the Design Lead, two Payments PMs, and a Thomas George / George Thomas name swap);
- `chats/` conversations, one JSON per chat (19 chats; CH1 and CH2 share a title on purpose, plus a near-duplicate non-trap title, two direct chats that are the on-call trap, a QA-lead direct chat and a second "Pod" group as first-match traps, and a CS-guild group and a security-lead direct chat that anchor two dependency chains);
- `emails/inbox.json` (71 emails, with same-day and same-topic clusters, look-deletable distractors, duplicate-subject pairs, cancelled/retracted threads, conflicting handover and org-chart threads, and the chain resolver and reply-target emails) and `emails/sent.json` (13);
- `calendar.json` events (27, multiple per day, each with an organizer, including a duplicate-title event pair, same-name planning/review near-misses, and the Partnerships review that anchors a dependency chain).

## Output

The agent writes `actions.json`, a JSON array of its write actions in order, each `{tool, args}` over `delete_email`, `update_contact`, `add_calendar_event`, `send_chat_message`, `reply_email`, `send_message_to_user`. Reads are never recorded or graded (ARE write-action verification).

## Verifier

`tests/` holds the ARE Verifier ported to Harbor RewardKit as two discovered dimensions, collapsed by `tests/reward.toml` (`[[reward]]` weighted mean) into the top-level `reward`:

- `tests/test_output/` the compiled, deterministic dimension (`test_output`): `are_verifier.py` is the stdlib engine, `test_output.py` registers one `@rk.criterion` per compiled fact, `oracle.json` is the normalized oracle DAG plus the compiled per-fact weight map. Facts: one `write_<id>` per unambiguous oracle write (hard match on the resolved anchor), one per remaining rigid argument (field, value, each calendar field, each attendee), `tool_name_count`, `causality`, one `no_guess_<AMB>` per ambiguity, and `message_sanity`, and one bounded work-conditional gate `no_unauthorized_writes`. It is scored as a plain weighted mean over 80 facts (total weight 143.08; each `no_guess` trap weighs `no_guess_each` = 2.0 and every routine fact weighs `base_each` = 1.0). The gate fact weighs 50.08, which is exactly 35% of the dimension by construction (`gate_fraction` = 0.35), and it is earned only when the submission commits no forbidden trap write and gets at least 60% of the unambiguous write anchors right, so it is a bounded share and not a sum-of-others cliff: no single fact is weighted as the sum of the others. The empty submission and a report-only abstention never earn it, while the oracle does. Committing one consequential wrong write with the rest of the work intact loses the gate plus that trap's `no_guess` and scores 0.6290, guessing all fourteen traps scores 0.4473, over-abstaining (report only, no clear writes) scores 0.2097 on merit, and the empty submission scores 0.0. The oracle earns the gate and scores 1.0.
- `tests/judge/judge.toml` the LLM-judge dimension (`judge`): a `codex` agent judge (`openai/gpt-6.1-sol`) scoring the free-text facets no file check can settle - the `send_message_to_user` report (identifies each ambiguity, explains each cause, claims no false completion, summarizes the real work, requests clarification), each chat body, and the reply bodies. Its credential is supplied at pilot via `tests/Dockerfile` and `[verifier.env]`; keyless, the compiled dimension alone produces the reward.

The cross-dimension split is set by `[judge].weight = 0.25`: RewardKit fixes a programmatic dimension's reward_weight at 1.0 and reads a judge dimension's from `[judge].weight`, so the split is test_output 80% : judge 20%. Per-criterion weight sums only normalize within a dimension and do not set the split. The reward is their weighted mean, written to `/logs/verifier/reward.json`.

## Dependency chains

Seven of the clear writes form three graded dependency chains (depth 2 to 3), each spanning more than one app, so the correct target of a dependent write is derivable only after an earlier ask is resolved. A mis-resolved first step propagates to the wrong derived target and fails the dependent writes too. The chain writes are ordinary weighted facts (no multiplier, none weighted as the sum of the others); no new write trips any existing abstention trap, and the chains are graded independently of the bounded work-conditional gate.

- Chain 1 (depth 3, chat to contacts to email to calendar): the CS Guild chat (CH18) names Divya Menon (C65) as the colleague taking over customer success, past the decoy Kiran Rao (C53, Support Lead, who keeps support). Step 1 promotes her to Head of Customer Success (A22, anchor C65). Step 2 replies to her onboarding plan email E068 (A23), whose id is derivable only once she is known, with Kiran's support summary E069 as the near-miss. Step 3 adds the CS kickoff on August 23 at 3 PM that E068 specifies (A24), co-hosted by the only Operations Manager Priya Menon (C28), with Operations Analyst C51 and Operations Lead C59 as near-misses.
- Chain 2 (depth 2, calendar to contacts to email): the only Partnerships review event (EV27) is organized by Rohan Kulkarni (C66), past the decoy attendee Neha Gupta (C25, Marketing Lead). Step 1 promotes him to Head of Partnerships (A25, anchor C66). Step 2 replies to his FinBridge pilot intro E070 (A26), derived from his identity, with Gaurav's Myriad growth fund intro E057 as the near-miss.
- Chain 3 (depth 2, email to contacts to chat): the compliance audit scope email E071 and the direct chat CH19 establish Nidhi Kapoor (C67) as the security lead running the audit, past the decoys Mohit Verma (C54, SRE) and Kabir Shah (C45, QA Lead). Step 1 promotes her to Head of Security (A27, anchor C67). Step 2 messages her one-on-one chat CH19 (A28), derived from her identity, with the QA Lead chat CH16 as the near-miss and the oncall chats CH13 and CH14 off limits as an existing trap.

The oracle earns all seven chain writes and their rigid-argument facts. The author-side conformance self-test (not part of the delivered bundle) recomputes the propagation by mis-resolving chain 2's first step to Neha (C25) and deriving its dependent reply from one of her own emails, which drops both the first-step and the dependent facts (0.9570 against the oracle 1.0).

## Run the oracle

Produce the reference submission and score it with the pinned RewardKit (compiled dimension, no judge key needed):

```sh
HARBOR_WORKSPACE=/tmp/ws sh solution/solve.sh          # writes /tmp/ws/actions.json
uvx --from 'harbor-rewardkit==0.1.7' rewardkit tests/test_output \
  --workspace /tmp/ws --output /tmp/ws/reward.json     # -> {"reward": 1.0}
```

The author-side conformance self-test (`solution/test_ar7.py`, not part of the delivered bundle; the shipped `tests/` surface is self-contained and grades without it) exercises the same engine over the oracle, an empty submission, per-write and per-argument mutants, the soft-field checks, and the first-match and second-match trap for every ambiguity; it proves every clear write resolves to exactly one target while every ambiguity stays genuinely non-unique, and it checks the judge dimension builds a codex AgentJudge with one criterion per grounding criterion, weights summing to 1, and `[judge].weight = 0.25`. `test_weights_scheme_work_conditional_gate` confirms the bounded gate fact `no_unauthorized_writes` is present, weighs between 30% and 40% of the dimension, and is work-conditional (a forbidden-clean submission under 60% anchors correct and a report-only run both fail it, while the oracle earns it), and that no single fact is weighted as the sum of the others. `test_score_curve` recomputes the curve (oracle 1.0, one consequential slip 0.6290, report-only 0.2097, empty 0.0) to confirm the gate is a bounded step and not a cliff. `test_dependency_chains` proves the oracle earns every dependency-chain fact and that mis-resolving a chain's first step propagates to its dependent writes, so both the first-step and dependent facts fail. The `no_unauthorized_writes` gate is bounded at 35% of the dimension and conditioned on real work, so difficulty rests on the dense universe, over-abstention, wrong-target, the per-trap `no_guess` facts, and the three dependency chains, with the gate rewarding completed work rather than acting as a side-effect multiplier.

Difficulty is pilot-measured, never author-claimed: no pass@1 figure is asserted here.
