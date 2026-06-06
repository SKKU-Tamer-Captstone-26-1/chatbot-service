from pathlib import Path

import pytest
from google.protobuf import json_format

from chatbot_service.server import load_generated_chatbot_grpc
from chatbot_service.validation.cli import main as validation_main
from chatbot_service.validation.evaluation import (
    ALLOWED_CHECKS,
    assert_response_matches_case,
    load_all_fixtures,
    validate_evaluation_fixtures,
)

ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = ROOT / "evaluation"


def test_evaluation_fixtures_cover_required_policy_checks():
    result = validate_evaluation_fixtures(EVALUATION_DIR)
    cases = load_all_fixtures(EVALUATION_DIR)
    checks = {check for case in cases for check in case["checks"]}

    assert result.passed is True
    assert result.case_count >= 10
    assert ALLOWED_CHECKS <= checks
    assert result.suites["golden_cases"] >= 2
    assert result.suites["price_inventory_uncertainty_cases"] >= 2


def test_evaluation_fixture_validation_rejects_missing_required_check(tmp_path):
    for filename in (
        "golden_cases.yaml",
        "no_answer_cases.yaml",
        "out_of_scope_cases.yaml",
        "ranking_integrity_cases.yaml",
        "korean_tone_cases.yaml",
        "price_inventory_uncertainty_cases.yaml",
    ):
        (tmp_path / filename).write_text(
            '- name: bad\n'
            '  user_message: "테스트"\n'
            '  expected_intent: "CHATBOT_INTENT_RECOMMEND_BEVERAGE"\n'
            '  expected_status: "CHATBOT_RESPONSE_STATUS_ANSWERED"\n'
            "  checks:\n"
            '    - "korean_tone"\n'
            "  max_answer_chars: 100\n"
            "  forbidden_answer_terms:\n"
            '    - "metadata"\n',
            encoding="utf-8",
        )

    result = validate_evaluation_fixtures(tmp_path)

    assert result.passed is False
    assert any("checks must include grounding" in failure for failure in result.failures)


def test_validation_cli_fixtures_command_passes(capsys):
    validation_main(["fixtures", "--evaluation-dir", str(EVALUATION_DIR)])

    output = capsys.readouterr().out
    assert '"passed": true' in output
    assert "ranking_integrity_cases" in output


def test_response_case_validation_accepts_grounded_ranking_case():
    generated = load_generated_chatbot_grpc()
    pb2 = generated.chatbot_pb2
    case = _case("beverage_rank_order_preserved")
    response = _beverage_response(pb2, answer="테스트 위스키를 먼저 추천드려요.")

    assert_response_matches_case(response, pb2, case)


def test_response_case_validation_rejects_reranked_cards():
    generated = load_generated_chatbot_grpc()
    pb2 = generated.chatbot_pb2
    case = _case("beverage_rank_order_preserved")
    response = _beverage_response(pb2, answer="테스트 위스키를 먼저 추천드려요.")
    response.cards[0].beverage_recommendation.rank = 3

    with pytest.raises(ValueError, match="ranks|order"):
        assert_response_matches_case(response, pb2, case)


def test_response_case_validation_enforces_korean_tone():
    generated = load_generated_chatbot_grpc()
    pb2 = generated.chatbot_pb2
    case = _case("concise_polite_recommendation_tone")
    response = _beverage_response(pb2, answer="This is an English answer.")

    with pytest.raises(ValueError, match="not Korean"):
        assert_response_matches_case(response, pb2, case)


def test_response_case_validation_enforces_price_uncertainty_warning():
    generated = load_generated_chatbot_grpc()
    pb2 = generated.chatbot_pb2
    case = _case("verified_price_observation_warning")
    response = _beverage_response(
        pb2,
        answer=(
            "검증된 가격 관측값 기준으로 테스트 위스키를 추천드려요.\n\n"
            "이 추천은 검증된 가격 관측값과 사람들의 경험적 의견을 바탕으로 "
            "만든 참고용 추천입니다. "
            "실제 매장 가격, 재고, 판매 여부는 달라질 수 있습니다."
        ),
        price_policy="verified_krw_observations_not_live_truth",
    )

    assert_response_matches_case(response, pb2, case)

    response.answer = "현재 판매가는 15000원이고 재고가 있습니다."
    with pytest.raises(ValueError, match="required term|overstated"):
        assert_response_matches_case(response, pb2, case)


def test_response_case_validation_enforces_inventory_uncertainty():
    generated = load_generated_chatbot_grpc()
    pb2 = generated.chatbot_pb2
    case = _case("uncertain_inventory_not_live_truth")
    response = pb2.AskChatbotResponse(
        intent=pb2.CHATBOT_INTENT_FIND_NEARBY_VENUE,
        status=pb2.CHATBOT_RESPONSE_STATUS_ANSWERED,
        answer="테스트 바틀샵 재고는 매장에 확인해 주세요.",
        cards=[
            pb2.ChatbotCard(
                card_type=pb2.CHATBOT_CARD_TYPE_VENUE_RECOMMENDATION,
                title="테스트 바틀샵",
                venue_recommendation=pb2.VenueRecommendationCard(
                    rank=1,
                    result_id="venue_result_1",
                    place_id="place_1",
                    name="테스트 바틀샵",
                    availability_status=pb2.VENUE_AVAILABILITY_STATUS_UNKNOWN,
                    freshness_status=pb2.VENUE_FRESHNESS_STATUS_STALE,
                ),
            )
        ],
    )
    response.used_sources.venue_result_ids.append("venue_result_1")

    assert_response_matches_case(response, pb2, case)

    response.answer = "테스트 바틀샵에 재고가 있습니다."
    with pytest.raises(ValueError, match="overstated|forbidden"):
        assert_response_matches_case(response, pb2, case)


def _case(name: str) -> dict:
    for case in load_all_fixtures(EVALUATION_DIR):
        if case["name"] == name:
            return case
    raise AssertionError(f"missing fixture case {name}")


def _beverage_response(
    pb2,
    *,
    answer: str,
    price_policy: str = "",
):
    response = pb2.AskChatbotResponse(
        intent=pb2.CHATBOT_INTENT_RECOMMEND_BEVERAGE,
        status=pb2.CHATBOT_RESPONSE_STATUS_ANSWERED,
        answer=answer,
        cards=[
            pb2.ChatbotCard(
                card_type=pb2.CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION,
                title="테스트 위스키",
                beverage_recommendation=pb2.BeverageRecommendationCard(
                    rank=1,
                    result_id="bev_result_1",
                    beverage_id="bev_1",
                    name_ko="테스트 위스키",
                ),
            ),
            pb2.ChatbotCard(
                card_type=pb2.CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION,
                title="테스트 진",
                beverage_recommendation=pb2.BeverageRecommendationCard(
                    rank=2,
                    result_id="bev_result_2",
                    beverage_id="bev_2",
                    name_ko="테스트 진",
                ),
            ),
            pb2.ChatbotCard(
                card_type=pb2.CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION,
                title="테스트 사케",
                beverage_recommendation=pb2.BeverageRecommendationCard(
                    rank=3,
                    result_id="bev_result_3",
                    beverage_id="bev_3",
                    name_ko="테스트 사케",
                ),
            ),
        ],
    )
    response.used_sources.beverage_result_ids.extend(
        ["bev_result_1", "bev_result_2", "bev_result_3"]
    )
    if price_policy:
        metadata = {
            "source": {
                "price_min_krw": 15000,
                "price_max_krw": 25000,
                "price_policy": price_policy,
            }
        }
        json_format.ParseDict(metadata, response.cards[0].metadata)
        json_format.ParseDict(metadata, response.cards[0].beverage_recommendation.metadata)
    return response
