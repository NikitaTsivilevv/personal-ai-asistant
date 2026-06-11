import pytest

pipecat = pytest.importorskip("pipecat")  # skip if the 'call' extra isn't installed
from assistant_worker.call.pipeline import (  # noqa: E402  (import after importorskip)
    build_turn_analyzer,
    build_vad_analyzer,
)


def test_vad_analyzer_uses_tuned_params():
    vad = build_vad_analyzer()
    params = vad.params  # SileroVADAnalyzer stores VADParams on .params
    assert params.stop_secs <= 0.5
    assert 0.0 < params.confidence <= 1.0
    assert params.min_volume >= 0.0


def test_turn_analyzer_builds_or_falls_back():
    analyzer = build_turn_analyzer()
    assert analyzer is None or analyzer.__class__.__name__ == "LocalSmartTurnAnalyzerV3"
