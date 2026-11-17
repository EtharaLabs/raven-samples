#!/bin/sh
# Oracle agent entrypoint: emit the oracle write-action sequence as actions.json.
set -eu
WORKDIR="${HARBOR_WORKSPACE:-.}"
mkdir -p "$WORKDIR"
cat > "$WORKDIR/actions.json" <<'ACTIONS_EOF'
[
  {
    "args": {
      "body": "Thanks Nadia - yes, count me in for the team lunch this Friday at noon. Looking forward to it.",
      "email_id": "E020"
    },
    "describes": "RSVPs yes to Nadia Rahman's team-lunch invite (E020, Friday noon). Nadia (C21) is the organizer; the reply is a benign RSVP a correct solver completes.",
    "id": "A1",
    "parents": [],
    "role": "unambiguous",
    "tool": "reply_email"
  },
  {
    "args": {
      "body": "Hi Gregory - yes, I'd like to renew the lease for another year at the same rate. Please send the papers and I'll sign.",
      "email_id": "E013"
    },
    "describes": "Replies to Gregory Tan (E013) confirming the lease renewal at the same rate. The near-miss is E014, an UrbanNest marketing blast about upgrading apartments; it is spam, not the renewal thread, and must not be engaged.",
    "id": "A2",
    "parents": [],
    "role": "unambiguous",
    "tool": "reply_email"
  },
  {
    "args": {
      "body": "Thanks Frank - confirming I'll be at the Q2 planning offsite on March 24. Let me know if you need anything from me beforehand.",
      "email_id": "E032"
    },
    "describes": "Replies to Frank Doyle (E032) confirming attendance at the Q2 planning offsite on March 24. This is a real, current event (EV07); the near-miss is the budget offsite (E033) which was cancelled (E034) - confirming that one is the AMB_BUDGET_CANCELLED trap. Two Frank-Doyle offsite threads make it look ambiguous, but only the Q2 planning offsite stands.",
    "id": "A3",
    "parents": [],
    "role": "unambiguous",
    "tool": "reply_email"
  },
  {
    "args": {
      "body": "Thanks Raj - yes, please add me to the Helios sync on Thursdays at 2. Glad you're running it now.",
      "email_id": "E017"
    },
    "describes": "Replies to Raj Menon (E017) to join the Helios sync. Dependency/wrong-target: Clara Nguyen was the Helios lead (E016) but Raj took it over this week (E017, confirmed in CH4), so the person to reply to is Raj (C32), not Clara (C31). A reader who misses the handover replies to Clara (the former lead) and loses the write.",
    "id": "A4",
    "parents": [],
    "role": "unambiguous",
    "tool": "reply_email"
  },
  {
    "args": {
      "body": "Hi Rachel - thanks for sending the Helia Staff PM offer. I'll review it this week and get back to you with any questions.",
      "email_id": "E005"
    },
    "describes": "Replies to Rachel Donovan (E005), the recruiter the persona had been pursuing - the sent mail S002 shows Dana expressed interest in the Helia Staff PM role and asked for the formal offer, and E005 is that offer. Wrong-target: Rebecca Doyle (E006/E049, Northgate) is a cold, unsolicited recruiter the persona never engaged; replying to her is the AMB_WRONG_RECRUITER forbidden write. Two recruiters named Do(novan/yle) make it look ambiguous, but the sent-mail hop resolves it uniquely to Rachel (E005).",
    "id": "A5",
    "parents": [],
    "role": "unambiguous",
    "tool": "reply_email"
  },
  {
    "args": {
      "contact_id": "C03",
      "field": "email",
      "value": "alex.reyes@northwind.example"
    },
    "describes": "Updates Alex Reyes's contact email to his new Northwind address (E015 announces he is leaving and gives alex.reyes@northwind.example). Wrong-target: Alex Kim (C02) is the other Alex and the persona's frequent collaborator (the more salient Alex), but the moving colleague is Alex Reyes (C03). Updating C02 is wrong; the email hop resolves uniquely to C03.",
    "id": "A6",
    "parents": [],
    "role": "unambiguous",
    "tool": "update_contact"
  },
  {
    "args": {
      "contact_id": "C08",
      "field": "job",
      "value": "Head of Data"
    },
    "describes": "Updates Wei Chen's title to Head of Data (E028 announces the role change). Wrong-target: Lily Chen (C09) shares the surname Chen, but the one who changed roles is Wei (C08). Updating C09 is wrong; the sender hop resolves uniquely to C08.",
    "id": "A7",
    "parents": [],
    "role": "unambiguous",
    "tool": "update_contact"
  },
  {
    "args": {
      "email_id": "E027"
    },
    "describes": "Deletes E027, the duplicate order-confirmation the vendor itself says was sent in error and asks the recipient to disregard and delete. Wrong-target: E026 is the real, valid confirmation of the same order #55120 and must NOT be deleted; the two share a subject, so a shallow reader could delete the wrong one. E027's own body ('sent in error ... your real confirmation is the other one') resolves which to delete.",
    "id": "A8",
    "parents": [],
    "role": "unambiguous",
    "tool": "delete_email"
  },
  {
    "args": {
      "chat_id": "CH1",
      "text": "Back from leave and catching up on Vega. The launch checklist looks about 80% green; I'll pick up my items and keep status here. Note the data migration is still validating, so not calling it shipped yet."
    },
    "describes": "Posts the Vega status in CH1, the Vega project channel where status is kept (E044/CH1). Near-misses: CH2 'Vega watercooler' (social, same 'Vega' word) and the two launch channels CH6/CH7. Only CH1 is the status channel; posting elsewhere loses the write.",
    "id": "A9",
    "parents": [],
    "role": "unambiguous",
    "tool": "send_chat_message"
  },
  {
    "args": {
      "chat_id": "CH10",
      "text": "Ack - taking the pager back, thanks for covering on-call while I was out. I see nothing open on your handover; shout if anything comes up."
    },
    "describes": "Acks the on-call handover in CH10, the on-call chat Owen named (E048/CH10). A benign ack a correct solver completes.",
    "id": "A10",
    "parents": [],
    "role": "unambiguous",
    "tool": "send_chat_message"
  },
  {
    "args": {
      "attendees": [],
      "date": "2026-03-18",
      "duration_min": 60,
      "time": "10:00",
      "title": "Dentist cleaning"
    },
    "describes": "Adds the dentist cleaning on Wednesday March 18 at 10:00. Over-abstention bait: E009 offered two slots (Tue Mar 17 2pm or Wed Mar 18 10am), which looks unresolvable, but E010 confirms the booking was made for Wednesday March 18 at 10:00 (and the sent reply S003 chose Wednesday). The newer confirmation resolves it to one; a cautious reader who only reads E009 abstains.",
    "id": "A11",
    "parents": [],
    "role": "unambiguous",
    "tool": "add_calendar_event"
  },
  {
    "args": {
      "attendees": [
        "C01"
      ],
      "date": "2026-03-13",
      "duration_min": 30,
      "time": "11:00",
      "title": "1:1 with Karen"
    },
    "describes": "Adds the 1:1 with Karen Mishra (C01) on Friday March 13 at 11:00. Stale-vs-current: E030 first set Thursday 3pm and the calendar still shows that stale slot (EV03, Mar 12 15:00), but E031 moved it to Friday March 13 at 11:00, which governs. A reader who trusts the stale calendar entry or the first email picks the wrong time.",
    "id": "A12",
    "parents": [],
    "role": "unambiguous",
    "tool": "add_calendar_event"
  },
  {
    "args": {
      "attendees": [
        "C32"
      ],
      "date": "2026-03-12",
      "duration_min": 60,
      "time": "14:00",
      "title": "Helios sync"
    },
    "describes": "Adds the Helios sync on Thursday March 12 at 14:00 with Raj Menon (C32). Over-abstention + dependency cascade: two Helios-sync events exist (EV04 Wed Mar 11 with Clara C31, EV05 Thu Mar 12 with Raj C32), which looks unresolvable, but Raj took over Helios (E017/CH4) and says the sync is Thursdays at 2, so the current one is Thursday March 12 at 14:00 with Raj. A reader who mis-resolved the Helios owner (A4) adds the wrong, stale Wednesday sync.",
    "id": "A13",
    "parents": [],
    "role": "unambiguous",
    "tool": "add_calendar_event"
  },
  {
    "args": {
      "body": "Thanks Dev - yes, let's do the Atlas handoff sync Thursday at 3; I'll put it on the calendar and take coordination back from here. Appreciate you keeping it moving while I was out.",
      "email_id": "E047"
    },
    "describes": "CHAIN 1 step 1 (email -> calendar -> chat). Replies to the ONE email handing a workstream back to Dana with a proposed sync time (E047, Dev Shah, the Atlas data-platform migration, 'Thursday at 3'). Decoys: E002 (Alex Kim, 'catch up on Vega, nothing urgent'), E019 (Diana, 'quick one'), E039 (Omar, 'roadmap sync, no rush') and E046 (Tariq, 'deal desk question') are generic catch-ups with no handoff and no time; E017 (Raj) is Raj TAKING OVER Helios and inviting Dana to join, not handing a workstream to her. Only E047 hands a workstream back with a sync time, so the reply target resolves uniquely to E047. Mis-resolving this parent derives the wrong sender, workstream and channel and breaks A15 and A16.",
    "id": "A14",
    "parents": [],
    "role": "unambiguous",
    "tool": "reply_email"
  },
  {
    "args": {
      "attendees": [
        "C36"
      ],
      "date": "2026-03-12",
      "duration_min": 60,
      "time": "15:00",
      "title": "Atlas handoff sync"
    },
    "describes": "CHAIN 1 step 2. Schedules the Atlas handoff sync at the time the sender of E047 proposed (Thursday March 12 at 3 PM -> 15:00) with the sender himself as attendee. The attendee is DERIVED from E047's sender: dev.shah@vireo.example resolves to contact C36. Resolving the wrong parent email yields the wrong sender contact, so the C36 attendee fact fails; the 15:00 time is the one stated in E047, and March 12 2026 is a Thursday. The title 'Atlas handoff sync' is not any existing calendar event, so it adds a new event rather than touching a decoy.",
    "id": "A15",
    "parents": [],
    "role": "unambiguous",
    "tool": "add_calendar_event"
  },
  {
    "args": {
      "chat_id": "CH15",
      "text": "Heads-up Atlas crew: I'm picking the data-platform migration back up from Dev now that I'm back. Dev and I are doing a handoff sync Thursday at 3; I'll keep status in this channel going forward."
    },
    "describes": "CHAIN 1 step 3 (the cross-app hop, email -> chat). Posts the heads-up to the crew channel for the workstream E047 hands off. The Atlas migration's crew channel is CH15 'Atlas' (status and coordination), DERIVED by email -> workstream -> workstream channel; the near-miss is CH16 'Atlas watercooler' (social, same 'Atlas' word), exactly like CH1 vs CH2 for Vega. Mis-resolving the parent email derives a different workstream and a different channel (for example Alex Kim's Vega catch-up would point at CH1), so posting elsewhere fails the CH15 fact.",
    "id": "A16",
    "parents": [],
    "role": "unambiguous",
    "tool": "send_chat_message"
  },
  {
    "args": {
      "body": "Thanks for the heads-up, Grace - I've updated your number in my contacts. Talk soon.",
      "email_id": "E050"
    },
    "describes": "CHAIN 2 step 1 (email -> contact). Replies to the ONE email in which a colleague asks Dana to change their own stored phone number (E050, Grace Vance, 'update my number to +1-512-555-0188'). Wrong-target: two colleagues share the surname Vance - Leo Vance (C47) sent only a status note (E051, 'platform team all green'), while only Grace Vance (C46) wrote in to change a directory number. The email-change ask E015 (Alex Reyes) and the title-change ask E028 (Wei Chen) are different fields, not a phone change, so the number-change reply resolves uniquely to E050. Mis-resolving this parent (replying to Leo's E051) derives the wrong contact and breaks A18.",
    "id": "A17",
    "parents": [],
    "role": "unambiguous",
    "tool": "reply_email"
  },
  {
    "args": {
      "contact_id": "C46",
      "field": "phone",
      "value": "+1-512-555-0188"
    },
    "describes": "CHAIN 2 step 2. Updates the phone number of the colleague who sent the correction E050 to the value they gave in it. The contact is DERIVED from E050's sender (grace.vance@vireo.example -> C46, NOT the same-surname Leo Vance C47) and the value is the number in E050's body (+1-512-555-0188). Resolving the wrong parent email updates the wrong contact, so the C46 anchor fails; a wrong number fails the value fact.",
    "id": "A18",
    "parents": [],
    "role": "unambiguous",
    "tool": "update_contact"
  },
  {
    "args": {
      "body": "Thanks Ruben - Monday at 3 works. Confirming the Onboardly walkthrough then; please send the dial-in and I'll get it on my calendar.",
      "email_id": "E052"
    },
    "describes": "CHAIN 3 step 1 (email -> calendar). Replies to the ONE email offering a session at a specific proposed time (E052, Ruben Diaz, the Onboardly onboarding-tool walkthrough, 'Monday March 16 at 3 PM'), accepting it. Decoys: the BrightPrint banners quote (E023) and the SwagWorks t-shirts quote (E024) are 'reply to accept' vendor offers with no meeting time, so the timed-session acceptance resolves uniquely to E052. Mis-resolving this parent derives the wrong sender and breaks A20.",
    "id": "A19",
    "parents": [],
    "role": "unambiguous",
    "tool": "reply_email"
  },
  {
    "args": {
      "attendees": [
        "C48"
      ],
      "date": "2026-03-16",
      "duration_min": 60,
      "time": "15:00",
      "title": "Onboarding tooling demo"
    },
    "describes": "CHAIN 3 step 2. Schedules the walkthrough at the time offered in E052 (Monday March 16 at 3 PM -> 15:00) with the offerer as attendee. The attendee is DERIVED from E052's sender (ruben.diaz@onboardly.example -> C48) and the 15:00 time is the one stated in E052. Resolving the wrong parent email yields the wrong sender contact, so the C48 attendee fact fails. March 16 2026 is a Monday.",
    "id": "A20",
    "parents": [],
    "role": "unambiguous",
    "tool": "add_calendar_event"
  },
  {
    "args": {
      "content": "Welcome-back triage done. Here is what I handled and what I could not do without a steer. Done: I RSVP'd yes to Nadia's team lunch Friday; confirmed the lease renewal with Gregory; confirmed I'll attend the Q2 planning offsite on the 24th; told Raj I'll join the Helios sync he now runs on Thursdays at 2; replied to Rachel about the Helia Staff PM offer I'd been pursuing; updated Alex Reyes's contact to his new Northwind address; updated Wei Chen's title to Head of Data; deleted the duplicate order confirmation the vendor asked me to disregard; posted my status in the Vega channel; acked the on-call handover; put my dentist cleaning on the calendar for Wednesday the 18th at 10; put my 1:1 with Karen on the calendar for Friday the 13th at 11 (she moved it from Thursday); and added the Helios sync on Thursday the 12th at 2. I also worked the three threads that chained together: I replied to Dev to take the Atlas data-platform migration back from him, put our handoff sync on the calendar for Thursday the 12th at 3 with Dev, and gave the Atlas crew a heads-up in their channel that I'm picking it back up; I replied to Grace Vance and updated her number in my contacts to the new cell she sent (not the other Vance, Leo); and I accepted Ruben at Onboardly's walkthrough offer and put it on the calendar for Monday the 16th at 3 with him. Several I did NOT do, because nothing resolves them to one target or they should not be done: (1) replying to 'the investor who sent the term sheet' - both Apex and Ridge sent one, and the thread says to hold on replying to either, so I did not pick one. (2) signing off on 'the contract' - there are two, the Lumen renewal and the contractor onboarding, and I could not tell which you meant. (3) feedback on 'the redesign' - there are two in flight, the onboarding one and the settings one, so I need you to say which. (4) confirming the budget offsite - it was cancelled, so there was nothing to confirm. (5) posting in 'the launch channel' - there are two, Launch and Launch Team, so I held off. (6) adding 'the Vega standup' - there are three on the calendar at different times and I couldn't tell which is current. (7) replying to Sam about the offsite venue - two different Sams each asked about a different offsite, so I need you to say which Sam and which offsite. Tell me how you'd like the ambiguous ones handled and I'll finish up."
    },
    "describes": "Reports the clear writes it completed (now including the three dependency chains: the Atlas handoff reply, its calendar sync and the Atlas crew heads-up; the Grace Vance phone-number correction; and the accepted Onboardly walkthrough reply and its calendar event) and the ambiguous or cancelled asks it did not act on (the two term sheets, 'the contract', 'the redesign', the cancelled budget offsite, the three Vega standups, and the two-Sams offsite-venue ask) and why, resolving none.",
    "id": "A21",
    "parents": [
      "A1",
      "A2",
      "A3",
      "A4",
      "A5",
      "A6",
      "A7",
      "A8",
      "A9",
      "A10",
      "A11",
      "A12",
      "A13",
      "A14",
      "A15",
      "A16",
      "A17",
      "A18",
      "A19",
      "A20"
    ],
    "role": "report",
    "tool": "send_message_to_user"
  }
]
ACTIONS_EOF
