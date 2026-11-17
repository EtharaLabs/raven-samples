#!/bin/sh
# Oracle agent entrypoint: emit the oracle write-action sequence as actions.json.
set -eu
WORKDIR="${HARBOR_WORKSPACE:-.}"
mkdir -p "$WORKDIR"
cat > "$WORKDIR/actions.json" <<'ACTIONS_EOF'
[
  {
    "args": {
      "email_id": "E017"
    },
    "describes": "Deletes E017, the DataForge final invoice (DataForge is the vendor offboarded per the Pinewicket Ops chat and the sent wrap-up email)",
    "id": "A1",
    "parents": [],
    "role": "unambiguous",
    "tool": "delete_email"
  },
  {
    "args": {
      "email_id": "E018"
    },
    "describes": "Deletes E018, the DataForge data export notice from the offboarded vendor",
    "id": "A2",
    "parents": [],
    "role": "unambiguous",
    "tool": "delete_email"
  },
  {
    "args": {
      "email_id": "E028"
    },
    "describes": "Deletes E028, the DataForge account closure confirmation from the offboarded vendor",
    "id": "A3",
    "parents": [],
    "role": "unambiguous",
    "tool": "delete_email"
  },
  {
    "args": {
      "contact_id": "C24",
      "field": "job",
      "value": "Principal Engineer"
    },
    "describes": "Sets Karthik Iyer's job to Principal Engineer; he is the engineer who wrote the ledger-service RFC (E021 sender), not the other ledger-review attendee",
    "id": "A4",
    "parents": [],
    "role": "unambiguous",
    "tool": "update_contact"
  },
  {
    "args": {
      "contact_id": "C03",
      "field": "city",
      "value": "Bengaluru"
    },
    "describes": "Sets Kavya Nair's city to Bengaluru; she is the college friend who moved there (CH8), the only such college friend",
    "id": "A5",
    "parents": [],
    "role": "unambiguous",
    "tool": "update_contact"
  },
  {
    "args": {
      "contact_id": "C16",
      "field": "job",
      "value": "Talent Lead"
    },
    "describes": "Sets Tara Menon's job to Talent Lead; she is the only recruiter",
    "id": "A6",
    "parents": [],
    "role": "unambiguous",
    "tool": "update_contact"
  },
  {
    "args": {
      "attendees": [
        "C02"
      ],
      "date": "2024-08-15",
      "duration_min": 30,
      "time": "15:00",
      "title": "Design sync"
    },
    "describes": "Adds the 30-minute Design sync on 2024-08-15 at 15:00 with Arjun Rao, the only Design Lead",
    "id": "A7",
    "parents": [],
    "role": "unambiguous",
    "tool": "add_calendar_event"
  },
  {
    "args": {
      "attendees": [
        "C18",
        "C14"
      ],
      "date": "2024-08-14",
      "duration_min": 45,
      "time": "11:00",
      "title": "Budget review"
    },
    "describes": "Adds the 45-minute Budget review on 2024-08-14 at 11:00 with Harish Gupta (the only Finance Lead) and Lata Pillai (the only accountant)",
    "id": "A8",
    "parents": [],
    "role": "unambiguous",
    "tool": "add_calendar_event"
  },
  {
    "args": {
      "chat_id": "CH10",
      "text": "Release 2.4 looks good to ship, you are clear to go ahead."
    },
    "describes": "Messages CH10, the one-on-one direct chat with Rhea Kapoor, the only QA Engineer, that release 2.4 is good to ship",
    "id": "A9",
    "parents": [],
    "role": "unambiguous",
    "tool": "send_chat_message"
  },
  {
    "args": {
      "chat_id": "CH3",
      "text": "Heads up, the design review moved to Friday."
    },
    "describes": "Messages CH3, the Pinewicket Product Pod group, that the design review moved to Friday",
    "id": "A10",
    "parents": [],
    "role": "unambiguous",
    "tool": "send_chat_message"
  },
  {
    "args": {
      "body": "Thanks Nikhil, I will send the latest deck to the intros this week.",
      "email_id": "E009"
    },
    "describes": "Replies to E009, the fundraise intro follow-up from Nikhil Desai, promising the deck to the intros this week",
    "id": "A11",
    "parents": [],
    "role": "unambiguous",
    "tool": "reply_email"
  },
  {
    "args": {
      "email_id": "E027"
    },
    "describes": "Deletes E027, the team offsite receipt, whose expense is already filed",
    "id": "A12",
    "parents": [],
    "role": "unambiguous",
    "tool": "delete_email"
  },
  {
    "args": {
      "email_id": "E013"
    },
    "describes": "Deletes E013, the press query email, already handled directly",
    "id": "A13",
    "parents": [],
    "role": "unambiguous",
    "tool": "delete_email"
  },
  {
    "args": {
      "body": "Thanks Tara, the shortlist looks good, go ahead and schedule the onsite panel for the PM role.",
      "email_id": "E005"
    },
    "describes": "Replies to E005, the recruiter's candidate-shortlist email; C16 is the only recruiter and E005 is her only shortlist email (E034 offsite photos is the near-miss)",
    "id": "A14",
    "parents": [],
    "role": "unambiguous",
    "tool": "reply_email"
  },
  {
    "args": {
      "attendees": [
        "C11",
        "C28"
      ],
      "date": "2024-08-20",
      "duration_min": 60,
      "time": "14:00",
      "title": "Vendor transition review"
    },
    "describes": "Adds the 60-minute Vendor transition review on 2024-08-20 at 14:00 with Imran Sheikh (the only CloudSpan account manager, C11) and Priya Menon (the only Operations Manager, C28); Brightline/Northwind AMs and the Operations Analyst are the near-misses",
    "id": "A15",
    "parents": [],
    "role": "unambiguous",
    "tool": "add_calendar_event"
  },
  {
    "args": {
      "chat_id": "CH9",
      "text": "Confirming the component library review is on for Thursday, thanks for the drafts."
    },
    "describes": "Messages CH9, the only Design Guild chat, confirming the component library review for Thursday; the Pinewicket Product Pod (CH3) and the Arjun Rao direct chat (CH6) are the near-misses",
    "id": "A16",
    "parents": [],
    "role": "unambiguous",
    "tool": "send_chat_message"
  },
  {
    "args": {
      "contact_id": "C08",
      "field": "job",
      "value": "Senior Data Scientist"
    },
    "describes": "Sets Ananya Iyer's job to Senior Data Scientist; she is the organizer of the Analytics review event (EV03), the only such event; Meera Iyer (Data Analyst) and Alok Nair (Analytics Engineer) are the near-misses",
    "id": "A17",
    "parents": [],
    "role": "unambiguous",
    "tool": "update_contact"
  },
  {
    "args": {
      "body": "Thanks Aisha, the Q3 board deck is ready, I will share it ahead of the meeting.",
      "email_id": "E061"
    },
    "describes": "Replies to E061, the email from Aisha Khan (C60), who organizes the Q3 board meeting (EV25); the Q3 board deck review email E002 from Rahul Verma is the first-match trap",
    "id": "A18",
    "parents": [],
    "role": "unambiguous",
    "tool": "reply_email"
  },
  {
    "args": {
      "contact_id": "C61",
      "field": "job",
      "value": "Workplace Experience Lead"
    },
    "describes": "Sets Thomas George's job to Workplace Experience Lead; he is the only Office Manager and his start-note email E062 states the new title. Operations Manager C28 and Operations Lead C59 are role near-misses; landlord George Thomas (C13) is the name-swap near-miss",
    "id": "A19",
    "parents": [],
    "role": "unambiguous",
    "tool": "update_contact"
  },
  {
    "args": {
      "body": "Thanks Mohit, we are cleared to publish the pen-test report, go ahead.",
      "email_id": "E066"
    },
    "describes": "Replies to E066, the only pen-test findings email (from Mohit Verma, SRE); the NDA-review emails E019 and E051 are security-adjacent near-misses",
    "id": "A20",
    "parents": [],
    "role": "unambiguous",
    "tool": "reply_email"
  },
  {
    "args": {
      "contact_id": "C65",
      "field": "job",
      "value": "Head of Customer Success"
    },
    "describes": "CHAIN 1 step 1 (chat -> contacts). Sets Divya Menon (C65) to Head of Customer Success; she is the colleague appointed to run customer success per the CS Guild chat CH18. Derived target: the only person named as taking over customer success; Kiran Rao (C53, Support Lead, same chat, who keeps support) is the real decoy. Uniquely resolvable from CH18. Graded by write_A22, write_A22__field, write_A22__value.",
    "id": "A22",
    "parents": [],
    "role": "unambiguous",
    "tool": "update_contact"
  },
  {
    "args": {
      "body": "Thanks Divya, the customer success onboarding plan is approved, go ahead and roll it out.",
      "email_id": "E068"
    },
    "describes": "CHAIN 1 step 2 (contacts -> email), depends on A22. Replies to E068, the onboarding-plan email from the customer success lead resolved in step 1 (Divya C65). Derived anchor email_id: the right email is reachable only once the CS lead is known; E069 (Kiran's support escalation summary) is the near-miss. Graded by write_A23.",
    "id": "A23",
    "parents": [
      "A22"
    ],
    "role": "unambiguous",
    "tool": "reply_email"
  },
  {
    "args": {
      "attendees": [
        "C65",
        "C28"
      ],
      "date": "2024-08-23",
      "duration_min": 45,
      "time": "15:00",
      "title": "CS kickoff"
    },
    "describes": "CHAIN 1 step 3 (email -> calendar), depends on A23. Adds the 45-minute CS kickoff on 2024-08-23 at 15:00 specified in the body of E068, with the CS lead (Divya C65) and the only Operations Manager (Priya Menon C28); Operations Analyst C51 and Operations Lead C59 are the ops near-misses. The date, time, duration, and co-host are discoverable only by reading E068, which is reached through steps 1 and 2. Graded by write_A24 and its date, time, duration, and per-attendee facts.",
    "id": "A24",
    "parents": [
      "A23"
    ],
    "role": "unambiguous",
    "tool": "add_calendar_event"
  },
  {
    "args": {
      "contact_id": "C66",
      "field": "job",
      "value": "Head of Partnerships"
    },
    "describes": "CHAIN 2 step 1 (calendar -> contacts). Sets Rohan Kulkarni (C66) to Head of Partnerships; he is the organizer of the only Partnerships review event (EV27). Derived anchor contact_id from the calendar; Neha Gupta (C25, Marketing Lead) attends EV27 and is the real decoy. Graded by write_A25, write_A25__field, write_A25__value.",
    "id": "A25",
    "parents": [],
    "role": "unambiguous",
    "tool": "update_contact"
  },
  {
    "args": {
      "body": "Thanks Rohan, go ahead and kick off the FinBridge partnership pilot.",
      "email_id": "E070"
    },
    "describes": "CHAIN 2 step 2 (contacts -> email), depends on A25. Replies to E070, the partner pilot intro from the partnerships lead resolved in step 1 (Rohan Kulkarni C66). Derived anchor email_id: reachable only once the organizer is known; E057 (Gaurav's Myriad growth fund intro) is the 'intro' near-miss. Graded by write_A26.",
    "id": "A26",
    "parents": [
      "A25"
    ],
    "role": "unambiguous",
    "tool": "reply_email"
  },
  {
    "args": {
      "contact_id": "C67",
      "field": "job",
      "value": "Head of Security"
    },
    "describes": "CHAIN 3 step 1 (email -> contacts). Sets Nidhi Kapoor (C67) to Head of Security; she is the security lead running the compliance audit per E071 (scope for sign-off) and the CH19 direct chat. Derived target; Mohit Verma (C54, SRE, the pen-test sender) and Kabir Shah (C45, QA Lead) are the security-adjacent decoys who do not lead the audit. Graded by write_A27, write_A27__field, write_A27__value.",
    "id": "A27",
    "parents": [],
    "role": "unambiguous",
    "tool": "update_contact"
  },
  {
    "args": {
      "chat_id": "CH19",
      "text": "The compliance audit is cleared to start, thanks for getting the scope ready."
    },
    "describes": "CHAIN 3 step 2 (contacts -> chat), depends on A27. Messages CH19, the one-on-one direct chat with the security lead resolved in step 1 (Nidhi C67), that the audit is cleared to start. Derived anchor chat_id: reachable only once the security lead is known; the QA Lead direct chat CH16 is the near-miss (the oncall chats CH13 and CH14 are off limits as the AMB_ONCALL trap). Graded by write_A28.",
    "id": "A28",
    "parents": [
      "A27"
    ],
    "role": "unambiguous",
    "tool": "send_chat_message"
  },
  {
    "args": {
      "content": "Here is what I completed and what I could not do without a steer. Completed: I deleted the three DataForge emails from the vendor we offboarded, namely the final invoice, the data export notice, and the account closure, plus the team offsite receipt and the press query email. I updated Karthik Iyer, who wrote the ledger-service RFC, to Principal Engineer; set Kavya Nair's city to Bengaluru; changed Tara Menon, our recruiter, to Talent Lead; bumped Ananya Iyer, who organizes the Analytics review, to Senior Data Scientist; and set Thomas George, our office manager, to Workplace Experience Lead per his start note. I added a 30-minute Design sync on August 15 at 3 PM with Arjun Rao, our design lead; a 45-minute Budget review on August 14 at 11 AM with Harish Gupta and Lata Pillai; and a 60-minute Vendor transition review on August 20 at 2 PM with Imran Sheikh at CloudSpan and Priya Menon in operations. I messaged Rhea Kapoor, our QA engineer, on our one-on-one that release 2.4 is good to ship; posted in the Pinewicket Product Pod that the design review moved to Friday; and confirmed in the Design Guild that the component library review is on for Thursday. I replied to Nikhil Desai's fundraise intro follow-up that the deck goes to the intros this week; to Tara Menon's candidate shortlist that the onsite panel is good to schedule; to Aisha Khan, who organizes the Q3 board meeting, that the deck is ready; and to Mohit Verma's pen-test findings that we are cleared to publish. On the chained items: I set Divya Menon, who is taking over customer success per the CS Guild chat, to Head of Customer Success, replied to her onboarding plan to approve the rollout, and added the 45-minute CS kickoff on August 23 at 3 PM with her and Priya Menon in operations that the plan asked for; I set Rohan Kulkarni, who organizes the Partnerships review, to Head of Partnerships and replied to his FinBridge pilot intro to go ahead; and I set Nidhi Kapoor, the security lead running the compliance audit, to Head of Security and messaged her on our one-on-one that the audit is cleared to start. Could not do, and I did not guess on any: (1) two chats share the exact title Catch-up and Startup Updates, so the startup catch-up note has no single target; (2) the quarterly review has no resolvable date, next Tuesday has no anchor, and no time; (3) no email is from a Priya about the Q3 budget, the Priyas wrote about reconciliation and Q4 and the Q3 budget email is Harish's; (4) two investors each sent a term sheet, Vivek Menon at Northstar and Aditi Rao at Elevation; (5) the current backend on-call is contested between Pooja Reddy and Manish Rao; (6) the only vendor renewal email, from Northwind, says they are not renewing, so there is nothing to confirm; (7) two inbox emails share the subject CloudSpan invoice for July but carry different amounts and neither is marked the erroneous copy, so I cannot tell which to delete; (8) the two org chart emails, one from Engineering and one from HR, give our platform lead Arjun Menon different new titles with no tiebreaker; (9) two events are both titled Sprint planning; (10) two product designers each emailed work, Simran Kaur and Ishan Gupta; (11) the landlord's only lease email says they are selling the building and ending the lease, so there is no lease renewal to confirm; (12) the founder roundtable invite was cancelled, so there is nothing to RSVP to; (13) the usual weekly planning time conflicts between two coworkers' emails, one saying 4 PM and one 3 PM; (14) two people claim to be the current payments squad PM, Sandhya Pillai and Vivek Nair. Tell me which chat, the quarterly review date and time, which Q3 budget email, which investor, who is on-call, how to handle the Northwind and landlord messages, which CloudSpan invoice, Arjun Menon's correct title, which Sprint planning, which product designer, the weekly planning time, and which payments PM, and I will finish them."
    },
    "describes": "Reports all fourteen ambiguities and resolves none, after completing the twenty base writes and the seven dependency-chain writes",
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
      "A20",
      "A22",
      "A23",
      "A24",
      "A25",
      "A26",
      "A27",
      "A28"
    ],
    "role": "report",
    "tool": "send_message_to_user"
  }
]
ACTIONS_EOF
