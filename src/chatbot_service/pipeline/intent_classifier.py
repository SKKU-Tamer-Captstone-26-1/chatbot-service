from chatbot_service.domain.intents import ChatbotIntent


class IntentClassifier:
    """Rule-first MVP intent classifier.

    Later this can use a small classifier model, but keep the initial version
    deterministic and easy to audit.
    """

    def classify(self, message: str) -> ChatbotIntent:
        text = message.strip().lower()
        if not text:
            return ChatbotIntent.INSUFFICIENT_DATA
        if any(word in text for word in ["근처", "주변", "파는 곳", "살 수", "어디"]):
            return ChatbotIntent.FIND_NEARBY_VENUE
        if any(word in text for word in ["비교", "싼", "가까운", "가격", "거리"]):
            return ChatbotIntent.COMPARE_PURCHASE_OPTIONS
        if any(word in text for word in ["추천", "취향", "술"]):
            return ChatbotIntent.RECOMMEND_BEVERAGE
        return ChatbotIntent.OUT_OF_SCOPE
