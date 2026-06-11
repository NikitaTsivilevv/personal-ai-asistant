# Risks

Track material risks, impact, mitigation, and current status.

| Risk | Impact | Mitigation | Status |
|---|---|---|---|
| Compliance uncertainty for AI calls and recordings in Spain/EU | Product may be legally unsafe to operate commercially | Legal review before production/commercial use; conservative AI disclosure; avoid recording until policy is clear | Open |
| Over-disclosure of personal data during calls | Privacy/security harm | Policy engine, per-task allowed facts, approvals for sensitive facts, audit log | Open |
| Voice worker reliability during long calls | Failed calls and poor UX | Long-lived worker outside serverless; retries; recovery state in DB; health checks | Open |
| Latency in STT/LLM/TTS loop | Unnatural conversations | Choose low-latency providers; measure end-to-end latency; keep prompts/context small | Open |
| Cost runaway during hold music or silence | Unexpected bills | Hold/silence detection; cost tracking; pause expensive processing during waits | Open |
| Agent context bloat during development | Slow and inconsistent AI-assisted development | Hot/warm/cold docs; epic-driven context; session closeout workflow | Mitigated by docs scaffold |
| Provider pricing/model drift | Incorrect cost estimates or outdated implementation choices | Recheck provider docs before implementation and before production | Open |
| Turn detection loses early/short callee utterances | Callee repeats themselves, conversations feel broken | Tuned `VADParams` + `LocalSmartTurnAnalyzerV3` wired onto the user aggregator (PR #7; old `vad_analyzer=` kwarg was a silent no-op); InboundAudioProbe kept | Mitigated in code 2026-06-11, awaiting live validation |
| Small conversation LLM drifts out of caller role mid-call | Agent acts as the callee's receptionist; task fails, callee confused | Explicit role block + language-aware few-shot (PR #7); offline A/B shows haiku holds role 3/3 | Mitigated in code 2026-06-11, awaiting live multi-turn confirmation |
| High-sensitivity fact values present in LLM prompt | Prompt injection by callee could elicit them without approval | `[SENSITIVE]` marker + approval rule in prompt (done); structural value withholding until approval | Partially mitigated |
| Dev-stand fragility: network blips kill api process and quick-tunnel registration | Lost live-session time, silent dead stand | Worker queue loop hardened (2026-06-11); api/bot resilience + process supervision + named tunnel/VPS pending (D-12) | Open (api+bot found dead again 2026-06-11) |
| Scenario routing built but not wired into intake | All tasks evaluate on the `generic` policy profile; doctor/insurance/restaurant rules and scenario-scoped facts never activate | Wire scenario detection into `normalize.py`/intake so `structured_goal.scenario` is set (D-12) | Open (found 2026-06-11) |

