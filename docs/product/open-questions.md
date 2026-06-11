# Open Questions

Track unresolved product, architecture, provider, compliance, and UX questions.

## Product Interface

- ~~Which interface ships first: web dashboard, Telegram, or both?~~ Resolved 2026-06-11 (D-6): Telegram bot + minimal live-call web page.
- Is mobile-lite required for MVP, or is responsive web enough?

## Personal Data

- Which `profile_facts` may be stored for MVP: DNI, address, policy numbers, date of birth, phone number, medical preferences?
- Which profile facts require per-task consent before use?
- Should sensitive profile facts be encrypted field-by-field from day one?

## Recordings And Transcripts

- Store audio recordings, or only transcript + summary?
- If recordings are stored, what is the retention period?
- How will call recording consent be handled in Spain/EU?

## Approval Policy

- Which actions are allowed without approval for insurance, doctor, restaurant, and information-gathering scenarios?
- What should happen if approval is needed while the other party is waiting on the line?

## Calendar And Contacts

- Which calendar integration should come first: Google Calendar, Apple Calendar, Outlook, or manual calendar entries?
- Should contacts be imported or entered manually at first?

## Inbound Calls

- Use a separate assistant number or forward from a personal number?
- What information can the assistant reveal before caller identity is established?

## Provider And Stack

- ~~Which API/backend framework should be used for the MVP?~~ Resolved 2026-06-11 (D-8): FastAPI + aiogram (Python), minimal Next.js web.
- ~~Which telephony provider should be used for Spain first?~~ Resolved 2026-06-11 (D-5): Twilio.
- Which exact Deepgram/LLM/Cartesia models and prices to use - recheck pricing/latency right before EPIC-002 implementation (D-5 fixes the providers, not the models).

## Commercialization And Compliance

- What legal review is needed before production use in Spain/EU?
- What AI disclosure wording is required at call start and during transfers?
- What data retention and deletion controls are required before commercial use?

