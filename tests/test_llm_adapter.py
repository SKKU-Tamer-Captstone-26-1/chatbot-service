from chatbot_service.pipeline.llm_adapter import _extract_chat_completion_text


def test_extract_chat_completion_text_from_openai_compatible_payload():
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "추천 결과 기준으로 답변드릴게요.",
                }
            }
        ]
    }

    assert _extract_chat_completion_text(payload) == "추천 결과 기준으로 답변드릴게요."
