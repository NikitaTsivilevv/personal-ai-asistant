from assistant_evals.llm_client import PRICES_PER_MTOK, FakeChat, cost_usd


def test_fake_chat_replays_and_tracks_usage():
    chat = FakeChat(["hola", "adiós"])
    import asyncio

    r1 = asyncio.run(chat.respond("sys", [{"role": "user", "content": "x"}]))
    r2 = asyncio.run(chat.respond("sys", [{"role": "user", "content": "y"}]))
    assert (r1.text, r2.text) == ("hola", "adiós")
    assert chat.total_input_tokens > 0 and chat.total_output_tokens > 0


def test_cost_usd_uses_price_table():
    assert "claude-haiku-4-5" in PRICES_PER_MTOK
    usd = cost_usd("claude-haiku-4-5", input_tokens=1_000_000, output_tokens=0)
    assert usd == PRICES_PER_MTOK["claude-haiku-4-5"][0]
