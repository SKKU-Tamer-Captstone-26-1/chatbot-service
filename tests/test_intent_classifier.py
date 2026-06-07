from chatbot_service.domain.intents import ChatbotIntent
from chatbot_service.pipeline.intent_classifier import (
    IntentClassifier,
    infer_beverage_diversity_mode,
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


def test_classify_out_of_scope():
    classifier = IntentClassifier()

    assert classifier.classify("오늘 서울 날씨 알려줘") == ChatbotIntent.OUT_OF_SCOPE
    assert classifier.classify(" ") == ChatbotIntent.INSUFFICIENT_DATA


def test_infer_beverage_diversity_mode_for_follow_up():
    assert infer_beverage_diversity_mode("다른 술 추천해줘") == "DIFFERENT_STYLE"
    assert infer_beverage_diversity_mode("비슷한 향이 좋은 술 추천") == "MORE_LIKE_THIS"
    assert infer_beverage_diversity_mode("완전 새로운 분위기의 술") == "DIFFERENT_STYLE"
