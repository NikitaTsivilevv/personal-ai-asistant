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

- ~~Which actions are allowed without approval for insurance, doctor, restaurant, and information-gathering scenarios?~~ Resolved 2026-06-11 (D-10): declarative per-scenario rule profiles in `assistant_policy/rules/`; tune from live audit data (EPIC-003 phase D).
- ~~What should happen if approval is needed while the other party is waiting on the line?~~ Resolved 2026-06-11 (D-10): wait phrase + 120 s expiry -> approval row `expired`, agent wraps up gracefully and ends the call.

## Calendar And Contacts

- Which calendar integration should come first: Google Calendar, Apple Calendar, Outlook, or manual calendar entries?
- Should contacts be imported or entered manually at first?

## Inbound Calls

- Use a separate assistant number or forward from a personal number?
- What information can the assistant reveal before caller identity is established?

## Provider And Stack

- ~~Which API/backend framework should be used for the MVP?~~ Resolved 2026-06-11 (D-8): FastAPI + aiogram (Python), minimal Next.js web.
- ~~Which telephony provider should be used for Spain first?~~ Resolved 2026-06-11 (D-5): Twilio.
- ~~Which exact Deepgram/LLM/Cartesia models and prices to use?~~ Resolved 2026-06-11: Deepgram Nova-3 / Cartesia Sonic / gpt-4o-mini confirmed, ~$0.04/min landline all-in (`docs/research/2026-06-11-provider-pricing.md`). Partially reopened by D-11: conversation LLM is now claude-haiku-4-5 (OpenAI quota ran out); recheck per-minute cost if the model stays.
- Which conversation model is the floor for reliable caller-role fidelity: claude-haiku-4-5 with a tuned prompt, claude-sonnet-4-6, or gpt-4o-mini? (Live calls 2026-06-11: haiku drifts mid-call.) Partially answered 2026-06-11 (D-11 follow-up): offline A/B shows haiku holds the role 3/3 with the PR #7 few-shot — staying on haiku; needs live multi-turn confirmation.
- What pipecat VAD/smart-turn configuration reliably catches short callee replies ("si, dime") and speech overlapping the bot's first utterance? Addressed in code 2026-06-11 (PR #7: tuned `VADParams` + `LocalSmartTurnAnalyzerV3` wired onto the user aggregator; the old `vad_analyzer=` kwarg was a silent no-op); awaiting live validation.

## Evaluation And Scenario Routing

- How should the task scenario be detected at intake so the policy profiles activate: an LLM-extracted enum in `normalize.py`, a keyword heuristic, or an explicit user pick - and what is the fallback when ambiguous? (Today `scenario` is never set, so everything runs `generic`; see D-12.)
- Offline eval harness: how faithful must the LLM "callee simulator" be (tool-free single-turn vs full pipeline with tools/multi-turn), and which metrics gate a change (task success, policy correctness, role-holding, latency, cost)?
- Should the caller-role few-shot stay generic/booking-flavoured or become scenario-specific once eval can measure the trade-off?

## Commercialization And Compliance

- What legal review is needed before production use in Spain/EU?
- What AI disclosure wording is required at call start and during transfers?
- What data retention and deletion controls are required before commercial use?

