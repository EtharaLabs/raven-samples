# Quick brain-dump before my meetings

Okay, I'm slammed and about to disappear into back-to-backs, so I'm just going to dump everything rattling around in my head and trust you to sort it out. Please read through all of it first and work out for yourself what each piece actually needs and which app it lives in, because I'm never going to say "contact C12" or "email E009", I describe people and things the way I think of them and half of it you'll only pin down by cross-referencing across my apps. Everything is in this folder: `persona.json` is me, `contacts.json` is my address book, `chats/` is my conversations (one file each), `emails/inbox.json` and `emails/sent.json` are my mail, and `calendar.json` is my schedule. Dig around before you touch anything.

My inbox first, it's a disaster. We finally offboarded that vendor for good, so clear out every last thread of theirs still sitting in there, I never want to see their name again. There's also a duplicate CloudSpan invoice in there, get rid of the extra copy. I already filed the expense for the team offsite ages ago so that receipt email can go, and the press query one too, I dealt with that reporter myself. While you're in mail: the vendor wrote about our renewal, reply and confirm we're going ahead with it; and reply to Priya about the Q3 budget and tell her the numbers look right.

Then a pile of contact updates I keep forgetting. The engineer who wrote up the ledger-service RFC just made Principal Engineer, bump his title. Our recruiter is Talent Lead now, update that. The person we just brought in to run customer success should move up a level, set her to Head of Customer Success. Whoever runs our partnerships review got a step up too, make them Head of Partnerships. And the security lead running our compliance audit just got promoted, set her to Head of Security. Bump whoever organizes the analytics review up to Senior Data Scientist while you're at it. Our office manager starts a new role on Monday, change his title to that. My platform lead's title needs to match the latest org chart, sort that out. And my college friend who just moved down to Bengaluru still has her old city on file, fix it.

Calendar is a mess too. Put a 30-minute "Design sync" on August 15 at 3 PM with our design lead. A 45-minute "Budget review" on August 14 at 11 AM with our finance lead and our accountant. A 60-minute "Vendor transition review" on August 20 at 2 PM with the CloudSpan account manager and our ops manager. Add the quarterly review for next Tuesday. Shift my sprint planning to the afternoon. Put my weekly planning on at the usual time, make it 90 minutes. Oh, and set up a 30-minute call with the investor who sent over the term sheet.

On the comms side, drop a note in the product pod that the design review moved to Friday, and confirm in the Design Guild chat that the component library review is on for Thursday. On my one-on-one with the QA engineer, tell her release 2.4 is good to ship. The engineer who's currently on the backend on-call needs to hear the ledger service is stable again, message them. On my one-on-one with that security lead once you've placed her, let her know the audit's cleared to start. And shoot a quick message to my startup catch-up group that I'll be about ten minutes late to our next meet-up.

Replies I still owe people: the recruiter's candidate-shortlist email, tell her to go ahead and schedule the onsite panel. The VC who sent the fundraise intro follow-up, let him know I'll get the deck to the intros this week. Whoever's organizing the Q3 board meeting, tell them the deck is ready. The pen-test findings email, let them know we're cleared to publish the report. That new customer success lead's onboarding-plan email, tell her it's approved to roll out, and then go set up the kickoff that same plan asks for, with the operations colleague it names. That partnerships lead's pilot-intro email, tell him to go ahead with the pilot. The landlord, confirm we're renewing the office lease. RSVP yes to Sara's founder roundtable invite. Reply to the current payments-squad PM's handover note and say the audit passed. And one of my product designers emailed me their latest work, reply and tell them it looks great.

I know that's a lot and it's completely jumbled, sorry. Please finish everything that's genuinely clear, and do it before you write back to me. Some of this might turn out to be impossible, or might point at more than one thing once you actually look, and if so, don't guess and don't pick a reading on my behalf, just do the clear parts and in your final message tell me exactly which parts you couldn't do and why. I'd much rather you ask than get it wrong.

## How to record what you did

Write a file called `actions.json` in this folder: a JSON array of the write actions you took, in the order you took them. List only write actions, not the reads you did to work things out. Each entry is an object with a `tool` name and an `args` object:

- `delete_email` with `{"email_id": "<id>"}`
- `update_contact` with `{"contact_id": "<id>", "field": "<field>", "value": "<new value>"}`
- `add_calendar_event` with `{"title": "<t>", "date": "YYYY-MM-DD", "time": "HH:MM", "duration_min": <int>, "attendees": ["<contact_id>", ...]}`
- `send_chat_message` with `{"chat_id": "<id>", "text": "<message>"}`
- `reply_email` with `{"email_id": "<id>", "body": "<message>"}`
- `send_message_to_user` with `{"content": "<message>"}`

Your final message back to me is itself a `send_message_to_user` write action, and it should summarize what you did and flag anything you could not do. For example:

```json
[
  {"tool": "delete_email", "args": {"email_id": "E017"}},
  {"tool": "send_message_to_user", "args": {"content": "Done with most of it. A few things I couldn't do: ..."}}
]
```
