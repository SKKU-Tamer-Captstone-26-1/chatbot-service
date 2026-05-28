from chatbot_service.domain.intents import ChatbotIntent
from chatbot_service.domain.schemas import ChatbotAnswer, ChatbotCard
from chatbot_service.proto_converters import (
    answer_to_proto,
    conversation_message_to_proto,
    request_from_proto,
)
from chatbot_service.server import load_generated_chatbot_grpc


def test_request_from_proto_maps_optional_fields_enums_and_struct():
    generated = load_generated_chatbot_grpc()
    pb2 = generated.chatbot_pb2
    request = pb2.AskChatbotRequest(
        conversation_id="conversation_1",
        message="가성비 좋은 위스키 추천해줘",
        lat=37.5,
        lng=127.1,
        radius_m=1200,
        budget_hint_krw=40000,
        screen_context=pb2.SCREEN_CONTEXT_HOME,
        category="whiskey",
        beverage_limit=3,
        budget_mode=pb2.BUDGET_MODE_STRICT,
    )
    request.client_context.update({"surface": "home_modal"})

    converted = request_from_proto(request, pb2)

    assert converted.conversation_id == "conversation_1"
    assert converted.lat == 37.5
    assert converted.lng == 127.1
    assert converted.radius_m == 1200
    assert converted.budget_hint_krw == 40000
    assert converted.screen_context == "SCREEN_CONTEXT_HOME"
    assert converted.budget_mode == "BUDGET_MODE_STRICT"
    assert converted.client_context == {"surface": "home_modal"}


def test_answer_to_proto_maps_grounded_answer_cards_and_sources():
    generated = load_generated_chatbot_grpc()
    pb2 = generated.chatbot_pb2
    answer = ChatbotAnswer(
        conversation_id="conversation_1",
        message_id="message_1",
        intent=ChatbotIntent.RECOMMEND_BEVERAGE,
        answer="추천 결과 기준으로는 테스트 위스키가 잘 맞아요.",
        confidence=0.91,
        profile_status="PROFILE_STATUS_ACTIVE",
        cards=[
            ChatbotCard(
                card_type="CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION",
                title="테스트 위스키",
                subtitle="whiskey",
                display_reason="취향 프로필과 잘 맞아요.",
                reason_codes=["MATCHES_PROFILE"],
                metadata={"source": "recommendation-service"},
                detail={
                    "beverage_recommendation": {
                        "rank": 1,
                        "result_id": "result_1",
                        "beverage_id": "bev_1",
                        "name_ko": "테스트 위스키",
                        "category": "whiskey",
                        "score": 0.91,
                        "reason_codes": ["MATCHES_PROFILE"],
                        "explanation": "취향 프로필과 잘 맞아요.",
                    }
                },
            )
        ],
        used_sources={
            "profile_status": "PROFILE_STATUS_ACTIVE",
            "profile_revision": 7,
            "beverage_recommendation_request_id": "bev_req_1",
            "beverage_ids": ["bev_1"],
            "beverage_result_ids": ["result_1"],
            "reason_codes": ["MATCHES_PROFILE"],
        },
    )

    proto = answer_to_proto(answer, pb2)

    assert proto.conversation_id == "conversation_1"
    assert proto.message_id == "message_1"
    assert proto.intent == pb2.CHATBOT_INTENT_RECOMMEND_BEVERAGE
    assert proto.status == pb2.CHATBOT_RESPONSE_STATUS_ANSWERED
    assert proto.profile_status == pb2.PROFILE_STATUS_ACTIVE
    assert proto.cards[0].beverage_recommendation.result_id == "result_1"
    assert proto.cards[0].metadata["source"] == "recommendation-service"
    assert proto.used_sources.beverage_recommendation_request_id == "bev_req_1"
    assert list(proto.used_sources.beverage_result_ids) == ["result_1"]


def test_answer_to_proto_maps_purchase_option_cards_and_sources():
    generated = load_generated_chatbot_grpc()
    pb2 = generated.chatbot_pb2
    answer = ChatbotAnswer(
        conversation_id="conversation_1",
        message_id="message_1",
        intent=ChatbotIntent.COMPARE_PURCHASE_OPTIONS,
        answer="추천 결과 기준으로는 테스트 바틀샵이 가격이 좋아요.",
        confidence=0.88,
        profile_status="PROFILE_STATUS_ACTIVE",
        cards=[
            ChatbotCard(
                card_type="CHATBOT_CARD_TYPE_PURCHASE_OPTION",
                title="테스트 바틀샵",
                detail={
                    "purchase_option": {
                        "option_type": "VENUE_OPTION_TYPE_BEST_PRICE",
                        "result_id": "venue_result_1",
                        "beverage_id": "bev_1",
                        "beverage_name": "테스트 위스키",
                        "place_id": "place_1",
                        "place_name": "테스트 바틀샵",
                        "place_type": "bottle_shop",
                        "address": "서울시 중구",
                        "distance_m": 320.0,
                        "price_krw": 42000,
                        "availability_status": "VENUE_AVAILABILITY_STATUS_AVAILABLE",
                        "freshness_status": "VENUE_FRESHNESS_STATUS_FRESH",
                        "score": 0.88,
                        "reason_codes": ["BEST_PRICE"],
                        "explanation": "가장 저렴한 구매 선택지예요.",
                    }
                },
            )
        ],
        used_sources={
            "profile_status": "PROFILE_STATUS_ACTIVE",
            "profile_revision": 7,
            "venue_recommendation_request_id": "venue_req_1",
            "venue_result_ids": ["venue_result_1"],
            "place_ids": ["place_1"],
            "reason_codes": ["BEST_PRICE"],
        },
    )

    proto = answer_to_proto(answer, pb2)

    assert proto.intent == pb2.CHATBOT_INTENT_COMPARE_PURCHASE_OPTIONS
    assert proto.cards[0].purchase_option.result_id == "venue_result_1"
    assert proto.cards[0].purchase_option.place_id == "place_1"
    assert proto.cards[0].purchase_option.price_krw == 42000
    assert proto.used_sources.venue_recommendation_request_id == "venue_req_1"
    assert list(proto.used_sources.venue_result_ids) == ["venue_result_1"]


def test_conversation_message_to_proto_reads_persisted_metadata():
    generated = load_generated_chatbot_grpc()
    pb2 = generated.chatbot_pb2

    proto = conversation_message_to_proto(
        {
            "message_id": "message_1",
            "role": "ASSISTANT",
            "content": "답변",
            "metadata": {
                "intent": "RECOMMEND_BEVERAGE",
                "cards": [
                    {
                        "card_type": "CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION",
                        "title": "테스트 위스키",
                    }
                ],
                "used_sources": {
                    "profile_status": "PROFILE_STATUS_ACTIVE",
                    "beverage_result_ids": ["result_1"],
                },
            },
        },
        pb2,
    )

    assert proto.message_id == "message_1"
    assert proto.role == pb2.CHATBOT_MESSAGE_ROLE_ASSISTANT
    assert proto.intent == pb2.CHATBOT_INTENT_RECOMMEND_BEVERAGE
    assert proto.cards[0].title == "테스트 위스키"
    assert list(proto.used_sources.beverage_result_ids) == ["result_1"]
