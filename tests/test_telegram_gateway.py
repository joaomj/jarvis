"""Test TelegramGateway: command routing, skill suggestions, streaming."""
from src.telegram_gateway import generate_correlation_id


def test_correlation_id_generated():
    """Every inbound message gets a unique correlation_id."""
    cid1 = generate_correlation_id()
    cid2 = generate_correlation_id()
    assert cid1 != cid2
    assert len(cid1) > 0
