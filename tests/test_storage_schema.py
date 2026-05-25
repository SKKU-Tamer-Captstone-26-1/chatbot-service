from pathlib import Path


def test_storage_migration_defines_chatbot_owned_tables_only():
    migration = Path("migrations/001_create_chatbot_storage.sql").read_text()

    assert "chatbot_conversations" in migration
    assert "chatbot_messages" in migration
    assert "chatbot_retrieval_traces" in migration
    assert "chatbot_feedback_events" in migration
    assert "survey_answers" not in migration
    assert "place_inventory" not in migration
