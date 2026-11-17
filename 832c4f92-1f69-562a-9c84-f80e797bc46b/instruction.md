# Back from leave - help me dig out

Hi - I'm back today after two weeks off and my inbox, calendar and chats are a wreck. It's all in this folder as plain files: `persona.json` is me, `contacts.json` is my address book, `chats/` has my conversations (one file each), `emails/inbox.json` and `emails/sent.json` are my mail, and `calendar.json` is my schedule. I'm going to rattle off what's on my plate the way it's sitting in my head, not in any tidy order. For each thing, work out for yourself what it actually needs doing, which app it belongs in, and who or what it really points at - I refer to people and things the way I think of them, never by any id, there are a ton of near-duplicates (same first names, shared surnames, repeated subjects and event titles), and some records disagree with each other or got superseded. Don't guess, and don't invent anything that isn't in the files: when something resolves to one answer once you dig, go do it; when it's genuinely ambiguous, already cancelled, or the obvious target turns out to be the wrong one, leave it and tell me. Finish everything that's clear before you write back.

OK, brain dump. There's a team lunch someone's pulling together for Friday - RSVP me. An investor who sent us a term sheet is waiting on a reply to say we're interested, so take care of that. My landlord emailed about the lease ending - confirm we're renewing. Somebody kept one of my workstreams moving the whole time I was out and now wants to hand it back to me over a quick sync - reply and confirm I'll take it. There's a contract that's been sitting in my inbox needing my sign-off. And one of the team is leaving for a new company and sent me a new email address, so update their contact.

A few more rattling around. Post my status update in the Vega channel. Reply to the recruiter I'd actually been talking to about the role I was chasing. Send my feedback on the redesign. Someone on the team pinged me that their own contact details changed - reply to them. Confirm I'll be at the Q2 planning offsite. And book my dentist cleaning onto my calendar as a 60-minute slot.

Still going. That handoff sync from the person giving me back the workstream - put it on my calendar with them as a 60-minute event titled "Atlas handoff sync", at whatever time they proposed. Put my 1:1 with Karen on there too; I'm fairly sure she moved it. Whoever's running Helios these days, let them know I'll join their sync. Someone moved into a new role while I was out and asked me to fix their job title in my contacts - do that. And a vendor offered to walk me through their tool at a set time - reply and take them up on it.

Nearly there. Ack the on-call handover. There's a duplicate order confirmation cluttering my inbox; delete the one that isn't needed. Confirm I'll attend the budget offsite. That person who pinged about their details changing - go ahead and make the change in my address book, set their number to whatever they gave me. Add the Helios sync to my calendar. And now that the workstream's coming back to me, give that crew a heads-up in their own channel that I'm picking it back up.

Last handful, then I'll let you work. Reply to Sam about the offsite venue. Get that vendor walkthrough on my calendar with them as a 60-minute event titled "Onboarding tooling demo", at the time they offered. Post an update in the launch channel. And add the Vega standup to my calendar.

One thing before you dive in: some of these will look unresolvable at first and come clear once you dig, and some will look obvious but turn out to point at more than one thing, be already cancelled or stale, or just be the wrong target once you check the details. Don't force a write you can't make truthfully - tell me instead. Do the clear parts, and in your final message spell out exactly which ones you couldn't do and why. I'd much rather you ask than get it wrong.

## How to record what you did

Write a file called `actions.json` in this folder: a JSON array of the write actions you took, in order. List only write actions, not the reads you did to work things out. Each entry is an object with a `tool` name and an `args` object:

- `reply_email` with `{"email_id": "<id>", "body": "<message>"}`
- `send_chat_message` with `{"chat_id": "<id>", "text": "<message>"}`
- `add_calendar_event` with `{"title": "<t>", "date": "YYYY-MM-DD", "time": "HH:MM", "duration_min": <int>, "attendees": ["<contact_id>", ...]}`
- `update_contact` with `{"contact_id": "<id>", "field": "<field>", "value": "<new value>"}`
- `delete_email` with `{"email_id": "<id>"}`
- `send_message_to_user` with `{"content": "<message>"}`

Your final message back to me is itself a `send_message_to_user` write action; summarize what you did and flag anything you could not do and why.
