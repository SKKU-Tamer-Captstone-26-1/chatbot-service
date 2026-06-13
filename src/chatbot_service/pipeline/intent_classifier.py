from chatbot_service.domain.intents import ChatbotIntent


class IntentClassifier:
    """Guarded score-based intent classifier.

    Keep this deterministic and easy to audit. The scorer is intentionally small:
    it improves mixed Korean routing without letting an LLM own backend routing
    or recommendation truth.
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

        scores = {
            ChatbotIntent.COMPARE_PURCHASE_OPTIONS: _score_terms(text, _COMPARISON_SCORE_TERMS),
            ChatbotIntent.FIND_NEARBY_VENUE: _score_terms(text, _VENUE_SCORE_TERMS),
            ChatbotIntent.RECOMMEND_BEVERAGE: _score_terms(text, _BEVERAGE_SCORE_TERMS),
        }
        if _is_general_out_of_scope(text, scores):
            return ChatbotIntent.OUT_OF_SCOPE

        if _has_explicit_comparison(text) and scores[ChatbotIntent.COMPARE_PURCHASE_OPTIONS] >= 5:
            return ChatbotIntent.COMPARE_PURCHASE_OPTIONS
        if _has_strong_venue_purpose(text) and scores[ChatbotIntent.FIND_NEARBY_VENUE] >= 5:
            return ChatbotIntent.FIND_NEARBY_VENUE
        if _has_strong_beverage_purpose(text) and scores[ChatbotIntent.RECOMMEND_BEVERAGE] >= 5:
            return ChatbotIntent.RECOMMEND_BEVERAGE

        intent, score = max(scores.items(), key=lambda item: item[1])
        if score > 0:
            return intent
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
        return "BEVERAGE_DIVERSITY_MODE_DIFFERENT"
    if any(word in text for word in _LIKE_KEYWORDS):
        return "BEVERAGE_DIVERSITY_MODE_ADJACENT"
    if any(word in text for word in _DIFFERENT_STYLE_KEYWORDS):
        return "BEVERAGE_DIVERSITY_MODE_DIFFERENT"
    return "BEVERAGE_DIVERSITY_MODE_DIFFERENT" if is_diverse_beverage_request(text) else ""


def infer_beverage_flavor_direction(message: str) -> str:
    text = message.strip().lower()
    if not text:
        return ""
    for direction, keywords in _FLAVOR_DIRECTION_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return direction
    return ""


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _score_terms(text: str, weighted_terms: tuple[tuple[str, int], ...]) -> int:
    return sum(weight for term, weight in weighted_terms if term in text)


def _has_explicit_comparison(text: str) -> bool:
    return _contains_any(text, _EXPLICIT_COMPARISON_TERMS)


def _has_strong_venue_purpose(text: str) -> bool:
    return _contains_any(text, _STRONG_VENUE_TERMS)


def _has_strong_beverage_purpose(text: str) -> bool:
    return _contains_any(text, _STRONG_BEVERAGE_TERMS)


def _is_general_out_of_scope(text: str, scores: dict[ChatbotIntent, int]) -> bool:
    if not _contains_any(text, _GENERAL_OUT_OF_SCOPE_TERMS):
        return False
    service_score = max(scores.values(), default=0)
    has_service_action = _contains_any(text, _SERVICE_ACTION_TERMS)
    return service_score < 8 or not has_service_action


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

_EXPLICIT_COMPARISON_TERMS = (
    "비교",
    "비교해",
    "어느 쪽",
    "뭐가 더",
    "어디가 더",
    "가격 비교",
    "거리 비교",
)

_COMPARISON_SCORE_TERMS = (
    ("가격 비교", 8),
    ("거리 비교", 8),
    ("비교", 7),
    ("비교해", 7),
    ("어느 쪽", 6),
    ("뭐가 더", 6),
    ("어디가 더", 6),
    ("더 저렴", 5),
    ("가장 가까", 4),
    ("가까운 곳", 3),
    ("저렴", 3),
    ("싼", 3),
    ("가격", 1),
    ("거리", 1),
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

_STRONG_VENUE_TERMS = (
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
    "재고",
    "bottle shop",
    "bar",
    "pub",
)

_VENUE_SCORE_TERMS = (
    ("마실만한 곳", 8),
    ("마실 곳", 8),
    ("파는 곳", 8),
    ("살 수", 8),
    ("구매처", 8),
    ("판매처", 8),
    ("갈만한 곳", 7),
    ("보틀샵", 7),
    ("bottle shop", 7),
    ("근처", 6),
    ("주변", 6),
    ("장소", 6),
    ("술집", 6),
    ("매장", 6),
    ("가게", 5),
    ("위치", 5),
    ("재고", 5),
    ("어디", 4),
    ("바", 4),
    ("펍", 4),
    ("bar", 4),
    ("pub", 4),
    ("곳", 2),
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

_STRONG_BEVERAGE_TERMS = (
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
    "주류",
    "한잔",
    "맛",
    "향",
    "가격까지 고려",
    "가성비",
)

_BEVERAGE_SCORE_TERMS = (
    ("가격까지 고려", 5),
    ("가성비", 5),
    ("취향", 5),
    ("위스키", 5),
    ("와인", 5),
    ("맥주", 5),
    ("칵테일", 5),
    ("전통주", 5),
    ("보드카", 5),
    ("주류", 5),
    ("사케", 4),
    ("한잔", 4),
    ("한잔할", 4),
    ("맛", 4),
    ("향", 4),
    ("술", 4),
    ("진", 3),
    ("럼", 3),
    ("피트", 3),
    ("스모키", 3),
    ("달게", 3),
    ("달콤", 3),
    ("덜 달", 3),
    ("가볍", 3),
    ("산뜻", 3),
    ("묵직", 3),
    ("허브", 3),
    ("쓴맛", 3),
    ("추천", 1),
)

_GENERAL_OUT_OF_SCOPE_TERMS = (
    "날씨",
    "주식",
    "시장",
    "뉴스",
    "역사",
    "정치",
    "수학",
    "번역",
    "코딩",
    "숙제",
)

_SERVICE_ACTION_TERMS = (
    "추천",
    "취향",
    "근처",
    "주변",
    "장소",
    "파는 곳",
    "살 수",
    "마실 곳",
    "비교",
    "가격",
    "재고",
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

_FLAVOR_DIRECTION_KEYWORDS = (
    ("BEVERAGE_FLAVOR_DIRECTION_LIGHTER", ("가볍", "가벼", "산뜻", "라이트", "청량")),
    ("BEVERAGE_FLAVOR_DIRECTION_RICHER", ("묵직", "진하게", "리치", "풀바디")),
    (
        "BEVERAGE_FLAVOR_DIRECTION_LESS_SMOKY",
        ("덜 피트", "피트향은 줄", "피트 줄", "덜 스모키", "스모키 줄"),
    ),
    ("BEVERAGE_FLAVOR_DIRECTION_SMOKIER", ("스모키", "피트", "훈연", "연기")),
    ("BEVERAGE_FLAVOR_DIRECTION_LESS_SWEET", ("덜 달", "달지 않", "드라이", "담백")),
    ("BEVERAGE_FLAVOR_DIRECTION_SWEETER", ("더 달", "달게", "달콤", "스위트")),
    ("BEVERAGE_FLAVOR_DIRECTION_MORE_HERBAL_BITTER", ("허브", "허벌", "쌉쌀", "쓴맛", "비터")),
    ("BEVERAGE_FLAVOR_DIRECTION_BRIGHTER_FRUITY", ("상큼", "과일", "프루티", "밝은", "산미")),
)
