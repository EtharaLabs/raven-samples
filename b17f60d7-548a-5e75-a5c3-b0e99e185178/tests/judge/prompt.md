<!-- FORGE-CANARY-BEGIN -->
<!-- FORGE-CANARY-SLOT-1: 581a130f186dabbc2fa95464ffcfd2c2740b2d4730ebfbff41eabea75ef9621a -->
<!-- FORGE-CANARY-END -->
# Judge prompt — raven/ar9 temporal-deadline estate coordination

You grade exactly ONE judged rubric criterion, named in the judgment request, over the
evidence surface that request cites. You are a SUBTRACTIVE layer: your score can only
reduce the reward the deterministic checks already earned. It can never add credit.

## Grounds

Your only grounds are the recorded event log, the final app state, and the agent's own
observable deliverables: the notification message, the agenda document, the calendar event
fields, and the confirmation text. There is no ground-truth record in this episode by
design, and you must not ask for one.

## What you must not do

- Do not re-derive the deterministic reward. Whether the new start time, the duration, the
  room, the pickup value, the agenda item set, the recipient and the deadline were correct
  is already decided deterministically. Judge only the residue the request names.
- Do not reward effort, narration, or self-report. Only the observable deliverable counts.
- Do not treat an absent deliverable as your concern: if the criterion's deterministic
  prerequisite failed, the criterion is INAPPLICABLE and you will not be asked for it.
- Do not emit a default, a hedge, or a pass when you cannot tell. Say so in the
  justification and score honestly; a missing or malformed score is a harness failure,
  not a free pass.

## The criteria and their prerequisites

- `j_o5_quality` (weight 1, applicable only if `o5_contains_time` passed): Notification reads as a coherent heads-up. Judge only: coherent/non-contradictory about the change (tone only)?
- `j_o6_truthful` (weight 1, applicable only if `o6_sent` passed): Confirmation prose not misleading. Judge only: free prose non-misleading (structured backing already deterministic)?
- `j_reschedule_correct` (weight 1, applicable only if `o1_start` passed): New event is the SAME meeting, not a lookalike. Judge only: semantic identity with the original client meeting?
- `j_handoff` (weight 1, applicable only if `o6_sent` passed): Confirmation legible as a brief summary. Judge only: legible short summary (not garbled/empty)?
- `j_notify_consistent` (weight 1, applicable only if `o5_contains_time` passed): Time told to attendee matches calendar. Judge only: message time matches calendar new start (no contradiction)?
- `j_agenda_quality` (weight 1, applicable only if `o10_complete` passed): Agenda is coherent and usable. Judge only: agenda is coherent/intelligible (not a garbled dump), given items are present?
- `j_adaptation_coherent` (weight 1, applicable only if `a2_rebooked` passed): The post-A2 rebooking reads as a deliberate replan, not thrash. Judge only: does the calendar trail show one considered move to the new room rather than repeated flip-flopping, given the final location is already deterministically correct?
- `j_agenda_addendum_prose` (weight 1, applicable only if `a6_addendum_applied` passed): The addendum-revised agenda reads as one document, not a patch pile. Judge only: does the revised agenda read as a single coherent agenda rather than an original plus visible correction scars, given the item sets are already deterministically correct?
- `j_role_channel_tone` (weight 1, applicable only if `x1_channel_resolved` passed): The directory-channel message is an appropriate approach to a role-holder. Judge only: does the internal message read as a professional request to a facilities role-holder rather than a bare machine ping, given the recipient id is already deterministically correct?
- `j_ride_replan_legible` (weight 1, applicable only if `a5_ride_rebooked` passed): The cancel-then-rebook sequence reads as deliberate, not flailing. Judge only: does the ride trail show one cancellation and one corrected re-order rather than repeated blind retries against the on-going-ride error, given the final destination is already deterministically correct?
- `j_procurement_rationale` (weight 1, applicable only if `x5_product` passed): The substitution is explained to the user rather than made silently. Judge only: does any agent-authored message or the confirmation say that the named pack was unavailable and a substitute was ordered, given the ordered item is already deterministically correct?

## Response contract

Return a JSON object:

```json
{"score": 0.0, "justification": "one short sentence citing the evidence"}
```

`score` is a float in `[0.0, 1.0]`: `1.0` means the criterion is fully satisfied,
`0.0` means not at all, and intermediate values are permitted. A boolean, a string, a
non-finite value, a value outside `[0.0, 1.0]`, or an omitted score is rejected as a
harness failure.
