# Glossary

Shared terminology for product docs, specs, code, and agent sessions.

## Task

A user instruction delegated to the assistant, such as "call the insurance company and ask for the claim status."

## Task Run

One execution attempt for a task. A task can have multiple runs if the first call fails, retries later, or requires follow-up.

## Call

A concrete phone call handled through a telephony provider. Calls can be outbound or inbound.

## Voice Worker

A long-lived process that manages realtime phone sessions, streaming audio, STT, LLM interaction, TTS, call state, live events, and recovery.

## Approval

An explicit user confirmation required before the assistant performs a sensitive action.

## Policy Engine

The component that decides whether a proposed message, tool call, disclosure, or external action is allowed, blocked, or requires approval.

## Profile Fact

A stored fact about the user that may be used by the assistant, such as name, phone number, language preference, address, DNI, policy number, or scheduling preferences.

## Scenario

A reusable task pattern, such as insurance status call, doctor appointment, restaurant booking, or inbound call screening.

## AI Disclosure

The assistant's explicit statement that it is an AI assistant calling on behalf of the user, not the user or a human employee.

## Human Takeover

A live handoff where the user joins, receives, or takes control of the call.

## Whisper Instruction

A live instruction from the user to the assistant during a call, without necessarily taking over the call.

## Audit Log

A durable record of important system, assistant, policy, approval, and user decisions.

