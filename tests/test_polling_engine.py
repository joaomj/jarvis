"""Tests for polling engine."""
from src.polling_engine import PollingEngine


def test_polling_engine_can_be_created():
    """PollingEngine can be instantiated with a token."""
    engine = PollingEngine(bot_token="test:token")
    assert engine._token == "test:token"
    assert engine._running is False
    assert engine._offset == 0


def test_polling_engine_stop():
    """stop() sets _running to False."""
    engine = PollingEngine(bot_token="test:token")
    engine._running = True
    engine.stop()
    assert engine._running is False
