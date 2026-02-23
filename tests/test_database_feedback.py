"""Tests for database layer and feedback operations."""

from pathlib import Path

import pytest

from jarvis.database import Database


class TestDatabase:
    """Tests for database layer."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database."""
        db_path = tmp_path / "test.db"
        return Database(str(db_path))

    def test_database_creation(self, db):
        """Test database file is created."""
        assert Path(db.db_path).exists()

    def test_user_management(self, db):
        """Test adding and checking users."""
        assert db.is_user_allowed(123) is False
        db.add_user(123)
        assert db.is_user_allowed(123) is True

    def test_message_logging(self, db):
        """Test message audit trail."""
        db.add_user(123)
        db.log_message(123, "in", "Hello")
        db.log_message(123, "out", "Hi there")
        assert db.get_user_message_count(123) == 2


class TestFeedbackOperations:
    """Tests for feedback operations."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database."""
        db_path = tmp_path / "test.db"
        return Database(str(db_path))

    def test_create_turn(self, db):
        """Test creating a feedback turn record."""
        turn_id = db.create_turn(
            telegram_user_id=12345,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="What is AI?",
            response_text="AI stands for Artificial Intelligence.",
        )
        assert turn_id > 0

        turn = db.get_turn(turn_id)
        assert turn is not None
        assert turn["telegram_user_id"] == 12345
        assert turn["telegram_chat_id"] == 67890
        assert turn["source"] == "opencode"
        assert turn["prompt_text"] == "What is AI?"
        assert turn["response_text"] == "AI stands for Artificial Intelligence."
        assert turn["vote"] is None

    def test_set_out_message_id(self, db):
        """Test setting outgoing message ID."""
        turn_id = db.create_turn(
            telegram_user_id=12345,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )
        db.set_out_message_id(turn_id, 99999)
        turn = db.get_turn(turn_id)
        assert turn["telegram_out_message_id"] == 99999

    def test_record_vote_authorized(self, db):
        """Test recording vote by authorized user."""
        turn_id = db.create_turn(
            telegram_user_id=12345,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )
        result = db.record_vote(turn_id, 12345, 1)
        assert result is True
        turn = db.get_turn(turn_id)
        assert turn["vote"] == 1
        assert turn["voted_at"] is not None

    def test_record_vote_unauthorized(self, db):
        """Test that unauthorized user cannot vote."""
        turn_id = db.create_turn(
            telegram_user_id=12345,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )
        result = db.record_vote(turn_id, 99999, 1)
        assert result is False
        turn = db.get_turn(turn_id)
        assert turn["vote"] is None

    def test_record_vote_overwrite(self, db):
        """Test that vote can be overwritten (last vote wins)."""
        turn_id = db.create_turn(
            telegram_user_id=12345,
            telegram_chat_id=67890,
            source="opencode",
            prompt_text="Test",
            response_text="Response",
        )
        db.record_vote(turn_id, 12345, 1)
        db.record_vote(turn_id, 12345, -1)
        turn = db.get_turn(turn_id)
        assert turn["vote"] == -1
