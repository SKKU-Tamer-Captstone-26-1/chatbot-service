from chatbot_service.domain.intents import ChatbotIntent
from chatbot_service.pipeline.intent_classifier import (
    IntentClassifier,
    infer_beverage_diversity_mode,
    infer_beverage_flavor_direction,
)


def test_classify_beverage_by_preference_terms():
    classifier = IntentClassifier()

    assert classifier.classify("내 취향에 맞는 술 추천해줘") == ChatbotIntent.RECOMMEND_BEVERAGE
    assert classifier.classify("오늘 한잔 할래") == ChatbotIntent.RECOMMEND_BEVERAGE


def test_classify_venue_terms_before_beverage_terms():
    classifier = IntentClassifier()

    assert classifier.classify("근처 바 추천해줘") == ChatbotIntent.FIND_NEARBY_VENUE
    assert classifier.classify("주변에서 마실 곳 알려줘") == ChatbotIntent.FIND_NEARBY_VENUE
    assert (
        classifier.classify("보틀샵에서 살 수 있는 곳 추천")
        == ChatbotIntent.FIND_NEARBY_VENUE
    )


def test_classify_compare_request():
    classifier = IntentClassifier()

    assert classifier.classify("가격 비교해줘") == ChatbotIntent.COMPARE_PURCHASE_OPTIONS
    assert classifier.classify("어느 쪽이 더 저렴해") == ChatbotIntent.COMPARE_PURCHASE_OPTIONS


def test_classify_price_aware_beverage_recommendation_as_beverage():
    classifier = IntentClassifier()

    assert (
        classifier.classify("가격까지 고려해서 술 추천해줘")
        == ChatbotIntent.RECOMMEND_BEVERAGE
    )
    assert classifier.classify("가성비 좋은 술 추천해줘") == ChatbotIntent.RECOMMEND_BEVERAGE


def test_classify_inventory_and_purchase_questions_as_venue():
    classifier = IntentClassifier()

    assert classifier.classify("지금 재고 있는 곳 알려줘") == ChatbotIntent.FIND_NEARBY_VENUE
    assert (
        classifier.classify("이 위스키 살 수 있는 보틀샵 알려줘")
        == ChatbotIntent.FIND_NEARBY_VENUE
    )


def test_classify_general_knowledge_with_alcohol_terms_as_out_of_scope():
    classifier = IntentClassifier()

    assert classifier.classify("맥주의 역사 알려줘") == ChatbotIntent.OUT_OF_SCOPE


def test_classify_out_of_scope():
    classifier = IntentClassifier()

    assert classifier.classify("오늘 서울 날씨 알려줘") == ChatbotIntent.OUT_OF_SCOPE
    assert classifier.classify(" ") == ChatbotIntent.INSUFFICIENT_DATA


def test_infer_beverage_diversity_mode_for_follow_up():
    assert infer_beverage_diversity_mode("다른 술 추천해줘") == (
        "BEVERAGE_DIVERSITY_MODE_DIFFERENT"
    )
    assert infer_beverage_diversity_mode("비슷한 향이 좋은 술 추천") == (
        "BEVERAGE_DIVERSITY_MODE_ADJACENT"
    )
    assert infer_beverage_diversity_mode("완전 새로운 분위기의 술") == (
        "BEVERAGE_DIVERSITY_MODE_DIFFERENT"
    )


def test_infer_beverage_flavor_direction_for_follow_up():
    assert infer_beverage_flavor_direction("피트향은 줄이고 더 가벼운 걸로 추천해줘") == (
        "BEVERAGE_FLAVOR_DIRECTION_LIGHTER"
    )
    assert infer_beverage_flavor_direction("덜 피트한 쪽으로 추천해줘") == (
        "BEVERAGE_FLAVOR_DIRECTION_LESS_SMOKY"
    )
    assert infer_beverage_flavor_direction("더 달게 추천해줘") == (
        "BEVERAGE_FLAVOR_DIRECTION_SWEETER"
    )


def test_uses_previous_venue_intent_on_ambiguous_follow_up():
    classifier = IntentClassifier()

    assert (
        classifier.classify(
            "다른 곳 추천해줘",
            previous_intent=ChatbotIntent.FIND_NEARBY_VENUE,
        )
        == ChatbotIntent.FIND_NEARBY_VENUE
    )
    assert (
        classifier.classify(
            "다음 장소도 추천해줘",
            previous_intent=ChatbotIntent.COMPARE_PURCHASE_OPTIONS,
        )
        == ChatbotIntent.FIND_NEARBY_VENUE
    )


def test_preserves_beverage_intent_on_explicit_beverage_follow_up():
    classifier = IntentClassifier()

    assert (
        classifier.classify(
            "다른 술 추천해줘",
            previous_intent=ChatbotIntent.FIND_NEARBY_VENUE,
        )
        == ChatbotIntent.RECOMMEND_BEVERAGE
    )
