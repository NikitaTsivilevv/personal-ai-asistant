# Provider pricing recheck (Stage 2 plan A1)

**Date:** 2026-06-11
**Purpose:** Verify per-call cost assumptions from D-5 (~$0.04-0.13/min all-in) before first live calls.

## Per-provider rates (pay-as-you-go, verified 2026-06-11)

| Provider | Component | Rate | Notes |
|---|---|---|---|
| Twilio | Outbound to ES landline | $0.0178/min | Most restaurants/clinics are landline |
| Twilio | Outbound to ES mobile | $0.0486/min (origin EEA) / $0.18 (non-EEA origin) | Origin-based pricing; our Spanish number qualifies for the EEA rate |
| Twilio | Media Streams (bidirectional) | $0.004/min | Charged on top of voice minutes |
| Twilio | Number rental | from ~$1.15/mo | Exact Spain local-number price visible in console after registration |
| Deepgram | Nova-3 streaming STT | $0.0077/min | Charged on processed audio only; $200 free credit on signup |
| Cartesia | Sonic TTS | 1 credit/char; Pro plan $4-5/mo ≈ 133 min TTS | Effective ~$0.03/min of synthesized speech if fully used |
| OpenAI | gpt-4o-mini (conversation LLM) | $0.15/M input, $0.60/M output tokens | Negligible per call: a 5-min call is well under $0.01 |
| Anthropic | Task normalization + summaries | per-token, 1-2 short requests per task | Negligible per call |

## Estimated cost of a 5-minute call to a Spanish landline

- Twilio voice: 5 × $0.0178 = $0.089
- Twilio media stream: 5 × $0.004 = $0.020
- Deepgram STT: ~4 min of speech × $0.0077 ≈ $0.031
- Cartesia TTS: ~1.5 min agent speech ≈ $0.045 (or inside Pro plan quota)
- LLM: < $0.01

**Total: ≈ $0.19-0.20 per 5-min landline call (~$0.04/min), ≈ $0.35 to a mobile.**

## Conclusion vs D-5

Within the D-5 envelope of $0.04-0.13/min - at the cheap end for landlines. No model
changes needed: Deepgram Nova-3, Cartesia Sonic, gpt-4o-mini stay as configured.
No new DECISIONS entry required (no choice changed).

Watch-outs:

- ES mobile from a non-EEA origin number costs $0.18/min - keep the FROM number Spanish.
- Cartesia free tier is too small for real testing; Pro ($4-5/mo) is enough for dev.
- Deepgram's $200 signup credit covers all dev-phase STT.

## Sources

- [Deepgram pricing](https://deepgram.com/pricing); [Nova-3 breakdown](https://brasstranscripts.com/blog/deepgram-pricing-per-minute-2025-real-time-vs-batch)
- [Cartesia pricing](https://www.cartesia.ai/pricing); [Sonic-3 plan guide](https://www.eesel.ai/blog/cartesia-sonic-3-pricing)
- [Twilio voice pricing - Spain](https://www.twilio.com/en-us/voice/pricing/es)
- [Twilio Media Streams overview](https://help.twilio.com/articles/37993178513307)
- [OpenAI API pricing](https://openai.com/api/pricing/)
