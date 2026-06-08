"""Tests for config module."""
from config import settings


def test_settings_have_defaults():
    assert settings.PORT == 8080
    assert settings.HOST == "0.0.0.0"
    assert settings.OASIS_ALGORITHM == "HS256"
    assert settings.OASIS_TOKEN_EXPIRY_HOURS == 24
    assert settings.SWIFT_LLM_MODEL == "swift-fhs"
    assert settings.CHAT_MODEL == "nexus-chat"


def test_settings_db_path_resolved():
    assert settings.OASIS_DB_DIR != ""
    assert settings.OASIS_DB_PATH != ""
