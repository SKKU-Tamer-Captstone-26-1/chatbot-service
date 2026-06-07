import pytest

from chatbot_service.storage.memory_repository import InMemoryConversationRepository
from chatbot_service.storage.async_repository import AsyncConversationRepository


@pytest.mark.anyio
async def test_memory_repository_paginates_messages_and_deduplicates_feedback():
    repository = InMemoryConversationRepository()
    conversation_id = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_HOME",
    )
    first_message_id = await repository.append_message(
        conversation_id,
        "USER",
        "추천해줘",
        {},
    )
    await repository.append_message(conversation_id, "ASSISTANT", "답변", {})

    page, next_token = await repository.get_messages(
        user_id="user_123",
        conversation_id=conversation_id,
        page_size=1,
        page_token="",
    )
    assert page[0]["message_id"] == first_message_id
    assert next_token == "1"

    feedback_id, duplicate = await repository.record_feedback(
        user_id="user_123",
        message_id=first_message_id,
        event_type="HELPFUL",
        idempotency_key="idem-1",
        metadata={},
    )
    duplicate_feedback_id, duplicate_second = await repository.record_feedback(
        user_id="user_123",
        message_id=first_message_id,
        event_type="HELPFUL",
        idempotency_key="idem-1",
        metadata={},
    )
    assert duplicate is False
    assert duplicate_second is True
    assert duplicate_feedback_id == feedback_id


@pytest.mark.anyio
async def test_memory_repository_scopes_reads_and_feedback_to_user():
    repository = InMemoryConversationRepository()
    conversation_id = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_HOME",
    )
    message_id = await repository.append_message(conversation_id, "ASSISTANT", "답변", {})

    page, next_token = await repository.get_messages(
        user_id="other_user",
        conversation_id=conversation_id,
        page_size=10,
        page_token="",
    )
    assert page == []
    assert next_token == ""

    with pytest.raises(ValueError, match="message_id"):
        await repository.record_feedback(
            user_id="other_user",
            message_id=message_id,
            event_type="HELPFUL",
            idempotency_key="idem-2",
            metadata={},
        )

    with pytest.raises(ValueError, match="conversation_id"):
        await repository.create_or_get_conversation(
            user_id="other_user",
            conversation_id=conversation_id,
            screen_context="SCREEN_CONTEXT_HOME",
        )


@pytest.mark.anyio
async def test_memory_repository_get_latest_conversation_for_user_and_screen():
    repository = InMemoryConversationRepository()
    await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_CHAT",
    )
    second = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_CHAT",
    )
    other_context = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_HOME",
    )

    assert await repository.get_latest_conversation_id_for_user(
        user_id="user_123",
        screen_context="SCREEN_CONTEXT_CHAT",
    ) == second
    assert await repository.get_latest_conversation_id_for_user(
        user_id="user_123",
        screen_context="SCREEN_CONTEXT_HOME",
    ) == other_context
    assert await repository.get_latest_conversation_id_for_user(
        user_id="user_123",
        screen_context="SCREEN_CONTEXT_UNSPECIFIED",
    ) == other_context
    assert await repository.get_latest_conversation_id_for_user(
        user_id="user_123",
        screen_context="SCREEN_CONTEXT_BOARD",
    ) == ""


@pytest.mark.anyio
async def test_async_conversation_repository_get_latest_conversation_for_user():
    inner = InMemoryConversationRepository()
    repository = AsyncConversationRepository(inner)

    first = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_CHAT",
    )
    second = await repository.create_or_get_conversation(
        user_id="user_123",
        conversation_id=None,
        screen_context="SCREEN_CONTEXT_CHAT",
    )

    assert await repository.get_latest_conversation_id_for_user(
        user_id="user_123",
        screen_context="SCREEN_CONTEXT_CHAT",
    ) == second
    await repository.close()
    assert first and second
