from chatbot_service.domain.intents import ChatbotIntent


class IntentClassifier:
    """Rule-first intent classifier.

    Keep this deterministic and easy to audit. A model-based classifier can be
    added later, but backend routing must remain explainable because a wrong
    route can make a venue question look like a beverage recommendation.
    """

    def classify(
        self,
        message: str,
        *,
        previous_intent: ChatbotIntent | None = None,
    ) -> ChatbotIntent:
        text = message.strip().lower()
        if not text:
            return ChatbotIntent.INSUFFICIENT_DATA
        if _is_followup_venue(message=text, previous_intent=previous_intent):
            return ChatbotIntent.FIND_NEARBY_VENUE
        if _contains_any(text, _COMPARISON_KEYWORDS):
            return ChatbotIntent.COMPARE_PURCHASE_OPTIONS
        if _contains_any(text, _VENUE_KEYWORDS):
            return ChatbotIntent.FIND_NEARBY_VENUE
        if _contains_any(text, _BEVERAGE_KEYWORDS) or _contains_any(
            text, _BEVERAGE_ALT_KEYWORDS
        ):
            return ChatbotIntent.RECOMMEND_BEVERAGE
        return ChatbotIntent.OUT_OF_SCOPE


def is_diverse_beverage_request(message: str) -> bool:
    text = message.strip().lower()
    if not text:
        return False
    return any(word in text for word in _DIVERSE_BEVERAGE_KEYWORDS)


def infer_beverage_diversity_mode(message: str) -> str:
    text = message.strip().lower()
    if not text:
        return ""
    if any(word in text for word in _EXPERIMENTAL_DIVERSITY_KEYWORDS):
        return "EXPLORE"
    if any(word in text for word in _LIKE_KEYWORDS):
        return "MORE_LIKE_THIS"
    if any(word in text for word in _DIFFERENT_STYLE_KEYWORDS):
        return "DIFFERENT_STYLE"
    return "DIFFERENT_STYLE" if is_diverse_beverage_request(text) else ""


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _is_followup_venue(message: str, previous_intent: ChatbotIntent | None) -> bool:
    if previous_intent not in {
        ChatbotIntent.FIND_NEARBY_VENUE,
        ChatbotIntent.COMPARE_PURCHASE_OPTIONS,
    }:
        return False

    if _contains_any(message, _BEVERAGE_FOLLOWUP_DISAMBIGUATORS):
        return False

    return _contains_any(message, _VENUE_FOLLOWUP_KEYWORDS)


_COMPARISON_KEYWORDS = (
    "비교",
    "비교해",
    "어느 쪽",
    "뭐가 더",
    "싼",
    "저렴",
    "가격",
    "거리",
    "가까운 곳",
    "가장 가까",
)

_VENUE_KEYWORDS = (
    "근처",
    "주변",
    "장소",
    "어디",
    "위치",
    "파는 곳",
    "살 수",
    "구매처",
    "판매처",
    "마실 곳",
    "마실만한 곳",
    "갈만한 곳",
    "바",
    "펍",
    "술집",
    "매장",
    "가게",
    "보틀샵",
    "bottle shop",
    "bar",
    "pub",
)

_BEVERAGE_KEYWORDS = (
    "추천",
    "취향",
    "술",
    "위스키",
    "와인",
    "맥주",
    "칵테일",
    "전통주",
    "사케",
    "진",
    "럼",
    "보드카",
)

_BEVERAGE_ALT_KEYWORDS = (
    "주류",
    "한잔",
    "한잔할",
    "한잔할래",
)

_BEVERAGE_FOLLOWUP_DISAMBIGUATORS = (
    "술",
    "위스키",
    "와인",
    "맥주",
    "칵테일",
    "전통주",
    "사케",
    "진",
    "럼",
    "보드카",
    "주류",
    "한잔",
    "한잔할",
    "한잔할래",
    "비슷한",
    "맛",
)

_DIVERSE_BEVERAGE_KEYWORDS = (
    "다른 장소",
    "다른 곳",
    "다른 술",
    "다른 추천",
    "다른거",
    "다른 게",
    "다른게",
    "또 다른",
    "다르게",
    "또 추천",
    "다르게 추천",
    "different",
)

_DIFFERENT_STYLE_KEYWORDS = (
    "다른 분위기",
    "다른 스타일",
    "색다른",
    "새로운",
    "취향 다른",
)

_LIKE_KEYWORDS = (
    "비슷한",
    "비슷하게",
    "비슷한 맛",
    "similar",
    "more like",
)

_EXPERIMENTAL_DIVERSITY_KEYWORDS = (
    "더 다양한",
    "기타 추천",
    "다양한",
    "탐색",
    "발품",
    "추천 뭐",
)

_VENUE_FOLLOWUP_KEYWORDS = (
    "다른 곳",
    "다른 장소",
    "다른 바",
    "다른 술집",
    "근처 다른",
    "다음 장소",
    "또 다른 곳",
    "다시 추천",
)
