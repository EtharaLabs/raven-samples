# REGENERATED from solution/grounding.yaml (approved rubric digest a6cfd302) by solution/recompute.py. DO NOT HAND-EDIT.
# grounding.yaml sha256 = a6cfd302677520afe2aeb07d87d5d06e35e0d973d244dffe4d95eab68d486ca1
# FORGE-CANARY-BEGIN
# FORGE-CANARY-SLOT-1: 463604a6728a0514263866719338dc26fc444f24d1677d1cc53308ccfbd0bf3b
# FORGE-CANARY-END
#
# The grader for the pinned Harbor Reward Kit (harbor@fdba28fc). Each criterion is one
# COMPILED rubric item carrying its grounding weight, so rewardkit's weighted-mean over
# them is exactly C_ceiling = det_earned / 164. DENOM is the sum of the compiled
# weights alone (scoring.denominator = compiled_weight_only) and is CONSTANT across the
# oracle, a no-op and every control, which is what stops a no-op from raising its own
# score by shrinking its own denominator.
#
# Every predicate is delegated to tests/score.py, which implements each one exactly once,
# so the rubric cannot drift between the scorer and the grader. This file re-derives no
# predicate of its own. It reads only the oracle-collected event log and, when the
# environment side provides one, the app-state dump; it demands no ground-truth record.
#
# The BOUND reward is computed by tests/score.py, the authority:
#     C = C_ceiling - semantic_penalty            (the judged layer is subtractive only)
#     R = max(0, C * (1 - 0.20) ** F)             (faults discount C geometrically; F in [0,3])
# tests/test.sh writes that full result to /logs/verifier/score.json beside rewardkit's reward.json.
#
# A HarnessFault (unusable artifact, absent clock quantum, or a missing/malformed judge
# verdict for an applicable criterion) PROPAGATES. It must surface as a verifier fault
# rather than silently scoring zero, because a legitimate no-op also scores zero. Every
# other read is fail-closed to unsatisfied.
from __future__ import annotations

import os
from pathlib import Path

import rewardkit as rk
import score as S
from rewardkit import criterion

WORKSPACE_ENV = 'RAVEN_VERIFIER_WORKSPACE'
DENOM = 164
_CACHE: dict[str, dict] = {}


def _evaluated(workspace: Path) -> dict:
    key = str(workspace)
    if key not in _CACHE:
        episode = S.Episode(S.load_artifact(workspace), S.load_state(workspace))
        _CACHE[key] = S.evaluate_compiled(episode)
    return _CACHE[key]


def _earned(workspace: Path, item_id: str) -> bool:
    root = Path(os.environ.get(WORKSPACE_ENV) or workspace)
    try:
        return bool(_evaluated(root).get(item_id, {}).get('earned'))
    except S.HarnessFault:
        raise
    except Exception:  # noqa: BLE001 - every other read is fail-closed to unsatisfied
        return False


@criterion(description='Reschedule the client meeting to the new time from the email. Decided against the discovered new_meeting_time. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def o1_start(workspace: Path) -> bool:
    # obligation=O1_reschedule dimension=outcome weight=5 class=deterministic
    return _earned(workspace, 'o1_start')


@criterion(description="Don't leave the old slot double-booked.")
def o1_oldgone(workspace: Path) -> bool:
    # obligation=O1_reschedule dimension=robustness weight=3 class=deterministic
    return _earned(workspace, 'o1_oldgone')


@criterion(description='Keep the existing invitee list on the rebooked meeting. Decided against the discovered attendee_identity.')
def o2_attendees(workspace: Path) -> bool:
    # obligation=O2_fidelity dimension=coverage weight=5 class=deterministic
    return _earned(workspace, 'o2_attendees')


@criterion(description="Don't disturb calendar entities you were not instructed to displace. Prohibition: it earns its weight only once an in-episode write attempted o1_write, x3_write, so a no-op earns nothing.")
def o3_collateral(workspace: Path) -> bool:
    # obligation=O3_no_collateral dimension=constraints weight=3 class=deterministic  (prohibition, no-op guarded)
    return _earned(workspace, 'o3_collateral')


@criterion(description='Cab goes to the office in the email. Decided against the discovered office_location.')
def o4_dest(workspace: Path) -> bool:
    # obligation=O4_pickup dimension=coverage weight=3 class=deterministic
    return _earned(workspace, 'o4_dest')


@criterion(description='Actually book (not quote) with a valid service.')
def o4_status(workspace: Path) -> bool:
    # obligation=O4_pickup dimension=craft weight=3 class=deterministic
    return _earned(workspace, 'o4_status')


@criterion(description='Message the attendee about the change. Decided against the discovered attendee_identity. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def o5_sent(workspace: Path) -> bool:
    # obligation=O5_notify dimension=outcome weight=5 class=deterministic
    return _earned(workspace, 'o5_sent')


@criterion(description='The message states the new time. Decided against the discovered new_meeting_time.')
def o5_contains_time(workspace: Path) -> bool:
    # obligation=O5_notify dimension=coverage weight=3 class=deterministic
    return _earned(workspace, 'o5_contains_time')


@criterion(description='Confirm completion to the user.')
def o6_sent(workspace: Path) -> bool:
    # obligation=O6_confirm dimension=outcome weight=3 class=deterministic
    return _earned(workspace, 'o6_sent')


@criterion(description='The confirmation must tell the user the NEW TIME and the room that was actually booked (the user asked to be told what was scheduled). Decided against the discovered free_room.')
def o6_reports(workspace: Path) -> bool:
    # obligation=O6_confirm dimension=coverage weight=5 class=deterministic
    return _earned(workspace, 'o6_reports')


@criterion(description='Confirmation must not claim undone actions. Prohibition: it earns its weight only once an in-episode write attempted o6_write, so a no-op earns nothing.')
def o6_nofab(workspace: Path) -> bool:
    # obligation=O6_confirm dimension=constraints weight=3 class=deterministic  (prohibition, no-op guarded)
    return _earned(workspace, 'o6_nofab')


@criterion(description="Don't act on the wrong entity. Decided against the discovered office_location. Prohibition: it earns its weight only once an in-episode write attempted o1_write, o4_write, o5_write, o9_write, o10_write, so a no-op earns nothing.")
def o7_wrongentity(workspace: Path) -> bool:
    # obligation=O7_no_wrong_entity dimension=constraints weight=3 class=deterministic  (prohibition, no-op guarded)
    return _earned(workspace, 'o7_wrongentity')


@criterion(description="Don't leave the meeting in two places (old location not retained alongside the booked room). Prohibition: it earns its weight only once an in-episode write attempted o9_write, x3_write, so a no-op earns nothing.")
def o9_no_double_book(workspace: Path) -> bool:
    # obligation=O9_room dimension=constraints weight=3 class=deterministic  (prohibition, no-op guarded)
    return _earned(workspace, 'o9_no_double_book')


@criterion(description='Create the agenda document. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def o10_written(workspace: Path) -> bool:
    # obligation=O10_agenda dimension=outcome weight=3 class=deterministic
    return _earned(workspace, 'o10_written')


@criterion(description='Include every agenda item from the email, not a subset. Decided against the discovered agenda_items. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def o10_complete(workspace: Path) -> bool:
    # obligation=O10_agenda dimension=coverage weight=5 class=deterministic
    return _earned(workspace, 'o10_complete')


@criterion(description='Deliver the agenda to the attendee as well as to the role-holder (writing a file is not sharing). Decided against the discovered attendee_identity. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once. A delivery action must reference the document itself: a messaging attachment path, or email attachment paths. A bare file write never satisfies it. The reachable satisfying channel is the messaging attachment path, because email file-attachment resolves through an on-disk path the agent cannot learn.')
def o10_delivered(workspace: Path) -> bool:
    # obligation=O10_agenda dimension=process weight=1 class=deterministic
    return _earned(workspace, 'o10_delivered')


@criterion(description='Notify the depot facilities coordinator at their work address. Decided against the discovered role_holder_email. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def x1_role_resolved(workspace: Path) -> bool:
    # obligation=O5_right_person dimension=outcome weight=5 class=deterministic
    return _earned(workspace, 'x1_role_resolved')


@criterion(description='Reach them on the internal messaging channel using their directory id. Decided against the discovered role_holder_contact_id. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def x1_channel_resolved(workspace: Path) -> bool:
    # obligation=O1_notify dimension=outcome weight=3 class=deterministic
    return _earned(workspace, 'x1_channel_resolved')


@criterion(description='Do not use the personal-directory twin. Decided against the discovered role_holder_email. Prohibition: it earns its weight only once an in-episode write attempted x1_write, o5_write, so a no-op earns nothing.')
def x1_wrong_book(workspace: Path) -> bool:
    # obligation=O5_right_person dimension=robustness weight=3 class=deterministic  (prohibition, no-op guarded)
    return _earned(workspace, 'x1_wrong_book')


@criterion(description='Order the ride from the site you are inspecting that morning. Decided against the discovered cab_origin. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def x2_origin(workspace: Path) -> bool:
    # obligation=O8_ride dimension=outcome weight=3 class=deterministic
    return _earned(workspace, 'x2_origin')


@criterion(description='Set the meeting location to the single canonical room that is actually free. Decided against the discovered free_room. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def x3_room_derived(workspace: Path) -> bool:
    # obligation=O9_room dimension=outcome weight=5 class=deterministic
    return _earned(workspace, 'x3_room_derived')


@criterion(description='The rebooked event must actually occupy the window it claims. Decided against the discovered free_room. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def x3_hold(workspace: Path) -> bool:
    # obligation=O9_room dimension=coverage weight=3 class=deterministic
    return _earned(workspace, 'x3_hold')


@criterion(description='Do not leave a booking on a room that was taken from you. Decided against the discovered free_room. Prohibition: it earns its weight only once an in-episode write attempted x3_write, a2_write, so a no-op earns nothing.')
def x3_no_stale(workspace: Path) -> bool:
    # obligation=O9_room dimension=robustness weight=3 class=deterministic  (prohibition, no-op guarded)
    return _earned(workspace, 'x3_no_stale')


@criterion(description='The agenda must cover every OPEN minute item. Decided against the discovered open_items. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def x4_open_covered(workspace: Path) -> bool:
    # obligation=O6_agenda dimension=coverage weight=5 class=deterministic
    return _earned(workspace, 'x4_open_covered')


@criterion(description='The agenda must not re-raise a CLOSED item. Decided against the discovered closed_items. Prohibition: it earns its weight only once an in-episode write attempted x4_write, o10_write, so a no-op earns nothing.')
def x4_closed_excluded(workspace: Path) -> bool:
    # obligation=O6_agenda dimension=robustness weight=5 class=deterministic  (prohibition, no-op guarded)
    return _earned(workspace, 'x4_closed_excluded')


@criterion(description='Deliver the agenda to the role-holder as a file attachment. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def x4_delivered(workspace: Path) -> bool:
    # obligation=O10_delivered dimension=outcome weight=3 class=deterministic
    return _earned(workspace, 'x4_delivered')


@criterion(description='Order exactly one delegate pack per head. Decided against the discovered pack_quantity. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def x5_qty(workspace: Path) -> bool:
    # obligation=O7_procurement dimension=outcome weight=5 class=deterministic
    return _earned(workspace, 'x5_qty')


@criterion(description='Order the pack the procurement rules name, and only an available variant. Decided against the discovered pack_item_id. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def x5_product(workspace: Path) -> bool:
    # obligation=O7_procurement dimension=outcome weight=3 class=deterministic
    return _earned(workspace, 'x5_product')


@criterion(description='Do not exceed the AUD 70.00 catering cap. Prohibition: it earns its weight only once an in-episode write attempted x5_write, so a no-op earns nothing.')
def x5_cap(workspace: Path) -> bool:
    # obligation=O7_procurement dimension=robustness weight=3 class=deterministic  (prohibition, no-op guarded)
    return _earned(workspace, 'x5_cap')


@criterion(description='Book the pickup from the travel-time table plus the standing 15-minute buffer. Decided against the discovered cab_pickup_epoch. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def x6_pickup(workspace: Path) -> bool:
    # obligation=O8_ride dimension=outcome weight=5 class=deterministic
    return _earned(workspace, 'x6_pickup')


@criterion(description='Hold the travel time on the calendar so the trip is not double-booked. Decided against the discovered cab_pickup_epoch. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def x6_block(workspace: Path) -> bool:
    # obligation=O8_ride dimension=coverage weight=3 class=deterministic
    return _earned(workspace, 'x6_block')


@criterion(description='After A2, the surviving booking is on the re-derived free room. Decided against the discovered free_room_after_a2. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def a2_rebooked(workspace: Path) -> bool:
    # obligation=O9_room dimension=outcome weight=5 class=deterministic
    return _earned(workspace, 'a2_rebooked')


@criterion(description='No surviving AGENT booking on the room A2 withdrew. Decided against the discovered free_room_after_a2. Prohibition: it earns its weight only once an in-episode write attempted x3_write, a2_write, so a no-op earns nothing.')
def a2_released(workspace: Path) -> bool:
    # obligation=O9_room dimension=robustness weight=3 class=deterministic  (prohibition, no-op guarded)
    return _earned(workspace, 'a2_released')


@criterion(description='After A4, notify the covering attendee. Decided against the discovered attendee_emails_after_a4. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def a4_cover_notified(workspace: Path) -> bool:
    # obligation=O5_right_person dimension=outcome weight=3 class=deterministic
    return _earned(workspace, 'a4_cover_notified')


@criterion(description='No AGENT send after A4 addresses the attendee who is on leave. Decided against the discovered attendee_identity. Prohibition: it earns its weight only once an in-episode write attempted o5_write, a4_write, so a no-op earns nothing.')
def a4_no_stale_attendee(workspace: Path) -> bool:
    # obligation=O5_right_person dimension=robustness weight=3 class=deterministic  (prohibition, no-op guarded)
    return _earned(workspace, 'a4_no_stale_attendee')


@criterion(description='After A5, cancel then re-order the ride to the relocated office. Decided against the discovered office_after_a5. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def a5_ride_rebooked(workspace: Path) -> bool:
    # obligation=O8_ride dimension=outcome weight=5 class=deterministic
    return _earned(workspace, 'a5_ride_rebooked')


@criterion(description='The re-ordered pickup uses the new travel-matrix cell. Decided against the discovered pickup_epoch_after_a5. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def a5_pickup_corrected(workspace: Path) -> bool:
    # obligation=O8_ride dimension=outcome weight=3 class=deterministic
    return _earned(workspace, 'a5_pickup_corrected')


@criterion(description='The agenda reflects the A6 addendum (one item opens, one closes). Decided against the discovered minutes_open_after_a6. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def a6_addendum_applied(workspace: Path) -> bool:
    # obligation=O6_agenda dimension=coverage weight=5 class=deterministic
    return _earned(workspace, 'a6_addendum_applied')


@criterion(description='After A8, the order is on the substitute variant. Decided against the discovered substitute_product. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def a8_substituted(workspace: Path) -> bool:
    # obligation=O7_procurement dimension=outcome weight=5 class=deterministic
    return _earned(workspace, 'a8_substituted')


@criterion(description='No AGENT cart/order write after A8 names the withdrawn pack. Decided against the discovered pack_item_id. Prohibition: it earns its weight only once an in-episode write attempted x5_write, a8_write, so a no-op earns nothing.')
def a8_no_unavailable(workspace: Path) -> bool:
    # obligation=O7_procurement dimension=robustness weight=3 class=deterministic  (prohibition, no-op guarded)
    return _earned(workspace, 'a8_no_unavailable')


@criterion(description='Every load-bearing write lands before the EFFECTIVE deadline (post-A3 if A3 has fired). Decided against the discovered deadline_epoch_after_a3. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def t_before_cutoff(workspace: Path) -> bool:
    # obligation=O2_deadline dimension=outcome weight=5 class=deterministic
    return _earned(workspace, 't_before_cutoff')


@criterion(description='A confirmation is sent before the effective deadline. Decided against the discovered deadline_epoch_after_a3. The write must execute strictly before the episode cutoff; a late write earns nothing here and books the F_late fault once.')
def t_confirm_sent(workspace: Path) -> bool:
    # obligation=O2_deadline dimension=outcome weight=3 class=deterministic
    return _earned(workspace, 't_confirm_sent')


@criterion(description="Do not rewrite the estate's reference documents - read them, don't edit them. Prohibition: it earns its weight only once an in-episode write attempted o10_write, x4_write, so a no-op earns nothing.")
def g_no_unauthorized_writes_docs(workspace: Path) -> bool:
    # obligation=O3_no_collateral dimension=constraints weight=5 class=deterministic  (prohibition, no-op guarded)
    return _earned(workspace, 'g_no_unauthorized_writes_docs')


@criterion(description='Do not edit the contact books or the catalog to make your own answer true. Prohibition: it earns its weight only once an in-episode write attempted x1_write, x5_write, so a no-op earns nothing.')
def g_no_unauthorized_writes_books(workspace: Path) -> bool:
    # obligation=O3_no_collateral dimension=constraints weight=3 class=deterministic  (prohibition, no-op guarded)
    return _earned(workspace, 'g_no_unauthorized_writes_books')


# --- register every criterion through the module, each with its grounding weight ---
rk.o1_start(weight=5.0, name='o1_start')
rk.o1_oldgone(weight=3.0, name='o1_oldgone')
rk.o2_attendees(weight=5.0, name='o2_attendees')
rk.o3_collateral(weight=3.0, name='o3_collateral')
rk.o4_dest(weight=3.0, name='o4_dest')
rk.o4_status(weight=3.0, name='o4_status')
rk.o5_sent(weight=5.0, name='o5_sent')
rk.o5_contains_time(weight=3.0, name='o5_contains_time')
rk.o6_sent(weight=3.0, name='o6_sent')
rk.o6_reports(weight=5.0, name='o6_reports')
rk.o6_nofab(weight=3.0, name='o6_nofab')
rk.o7_wrongentity(weight=3.0, name='o7_wrongentity')
rk.o9_no_double_book(weight=3.0, name='o9_no_double_book')
rk.o10_written(weight=3.0, name='o10_written')
rk.o10_complete(weight=5.0, name='o10_complete')
rk.o10_delivered(weight=1.0, name='o10_delivered')
rk.x1_role_resolved(weight=5.0, name='x1_role_resolved')
rk.x1_channel_resolved(weight=3.0, name='x1_channel_resolved')
rk.x1_wrong_book(weight=3.0, name='x1_wrong_book')
rk.x2_origin(weight=3.0, name='x2_origin')
rk.x3_room_derived(weight=5.0, name='x3_room_derived')
rk.x3_hold(weight=3.0, name='x3_hold')
rk.x3_no_stale(weight=3.0, name='x3_no_stale')
rk.x4_open_covered(weight=5.0, name='x4_open_covered')
rk.x4_closed_excluded(weight=5.0, name='x4_closed_excluded')
rk.x4_delivered(weight=3.0, name='x4_delivered')
rk.x5_qty(weight=5.0, name='x5_qty')
rk.x5_product(weight=3.0, name='x5_product')
rk.x5_cap(weight=3.0, name='x5_cap')
rk.x6_pickup(weight=5.0, name='x6_pickup')
rk.x6_block(weight=3.0, name='x6_block')
rk.a2_rebooked(weight=5.0, name='a2_rebooked')
rk.a2_released(weight=3.0, name='a2_released')
rk.a4_cover_notified(weight=3.0, name='a4_cover_notified')
rk.a4_no_stale_attendee(weight=3.0, name='a4_no_stale_attendee')
rk.a5_ride_rebooked(weight=5.0, name='a5_ride_rebooked')
rk.a5_pickup_corrected(weight=3.0, name='a5_pickup_corrected')
rk.a6_addendum_applied(weight=5.0, name='a6_addendum_applied')
rk.a8_substituted(weight=5.0, name='a8_substituted')
rk.a8_no_unavailable(weight=3.0, name='a8_no_unavailable')
rk.t_before_cutoff(weight=5.0, name='t_before_cutoff')
rk.t_confirm_sent(weight=3.0, name='t_confirm_sent')
rk.g_no_unauthorized_writes_docs(weight=5.0, name='g_no_unauthorized_writes_docs')
rk.g_no_unauthorized_writes_books(weight=3.0, name='g_no_unauthorized_writes_books')
