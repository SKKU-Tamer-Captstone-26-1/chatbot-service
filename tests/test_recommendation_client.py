import pytest

from chatbot_service.clients import recommendation_client as recommendation_client_module
from chatbot_service.clients.recommendation_client import (
    GrpcRecommendationClient,
    _channel_target,
    _load_generated_modules,
)


class FakeChannel:
    def __init__(self, target: str, secure: bool) -> None:
        self.target = target
        self.secure = secure
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeRecommendationStub:
    pb2 = None
    instances = []

    def __init__(self, channel: FakeChannel) -> None:
        self.channel = channel
        self.calls = []
        type(self).instances.append(self)

    async def GetProfileStatus(self, request, metadata, timeout):
        self.calls.append(("profile", request, metadata, timeout))
        return self.pb2.GetProfileStatusResponse(
            status=self.pb2.PROFILE_STATUS_ACTIVE,
            profile_revision=7,
        )

    async def GetBeverageRecommendations(self, request, metadata, timeout):
        self.calls.append(("beverage", request, metadata, timeout))
        return self.pb2.GetBeverageRecommendationsResponse(
            request_id="bev_req_1",
            profile_status=self.pb2.PROFILE_STATUS_ACTIVE,
            profile_revision=7,
            recommendations=[
                self.pb2.BeverageRecommendation(
                    rank=1,
                    result_id="result_1",
                    beverage_id="bev_1",
                    name_ko="테스트 위스키",
                    category="whiskey",
                    score=0.91,
                    reason_codes=["MATCHES_PROFILE"],
                )
            ],
        )

    async def GetVenueRecommendations(self, request, metadata, timeout):
        self.calls.append(("venue", request, metadata, timeout))
        return self.pb2.GetVenueRecommendationsResponse(
            request_id="venue_req_1",
            profile_status=self.pb2.PROFILE_STATUS_ACTIVE,
            profile_revision=7,
        )

    async def RecordRecommendationEvent(self, request, metadata, timeout):
        self.calls.append(("event", request, metadata, timeout))
        return self.pb2.RecordRecommendationEventResponse(
            interaction_id="interaction_1",
            duplicate=False,
        )


class FakeRecommendationGrpc:
    RecommendationServiceStub = FakeRecommendationStub


def test_channel_target_strips_http_schemes():
    assert _channel_target("http://recommendation:9090") == "recommendation:9090"
    assert _channel_target("https://recommendation.example") == "recommendation.example"
    assert _channel_target("recommendation:9090") == "recommendation:9090"


def test_recommendation_client_infers_tls_for_cloud_run_443():
    client = GrpcRecommendationClient("recommendation-service.example.com:443")

    assert client._target == "recommendation-service.example.com:443"
    assert client._secure is True


@pytest.mark.anyio
async def test_grpc_recommendation_client_maps_beverage_request(monkeypatch):
    pb2, _ = _load_generated_modules()
    FakeRecommendationStub.pb2 = pb2
    FakeRecommendationStub.instances = []

    monkeypatch.setattr(
        recommendation_client_module,
        "_build_channel",
        lambda target, secure: FakeChannel(target, secure),
    )
    client = GrpcRecommendationClient(
        "http://recommendation:9090",
        secure=False,
        timeout_ms=1234,
        recommendation_pb2=pb2,
        recommendation_pb2_grpc=FakeRecommendationGrpc,
    )

    response = await client.get_beverage_recommendations(
        {"authorization": "Bearer token"},
        category="whiskey",
        limit=3,
        budget_mode="BUDGET_MODE_STRICT",
    )

    stub = FakeRecommendationStub.instances[0]
    call_name, request, metadata, timeout = stub.calls[0]
    assert stub.channel.target == "recommendation:9090"
    assert stub.channel.secure is False
    assert call_name == "beverage"
    assert request.category == "whiskey"
    assert request.limit == 3
    assert request.budget_mode == pb2.BUDGET_MODE_STRICT
    assert metadata == [("authorization", "Bearer token")]
    assert timeout == 1.234
    assert response["request_id"] == "bev_req_1"
    assert response["profile_status"] == "PROFILE_STATUS_ACTIVE"
    assert response["recommendations"][0]["result_id"] == "result_1"


@pytest.mark.anyio
async def test_grpc_recommendation_client_maps_venue_and_event_requests(monkeypatch):
    pb2, _ = _load_generated_modules()
    FakeRecommendationStub.pb2 = pb2
    FakeRecommendationStub.instances = []

    monkeypatch.setattr(
        recommendation_client_module,
        "_build_channel",
        lambda target, secure: FakeChannel(target, secure),
    )
    client = GrpcRecommendationClient(
        "recommendation.example:443",
        secure=True,
        recommendation_pb2=pb2,
        recommendation_pb2_grpc=FakeRecommendationGrpc,
    )

    await client.get_venue_recommendations(
        {"x-user-id": "user_1"},
        lat=37.5,
        lng=127.1,
        selected_beverage_id="bev_1",
        radius_m=1500,
        limit=2,
        budget_mode="BUDGET_MODE_SOFT",
    )
    await client.record_recommendation_event(
        {"x-user-id": "user_1"},
        request_id="venue_req_1",
        result_id="venue_result_1",
        event_type="RECOMMENDATION_EVENT_TYPE_CLICK",
        idempotency_key="idem-1",
        metadata={"surface": "chatbot"},
    )

    stub = FakeRecommendationStub.instances[0]
    venue_call = stub.calls[0]
    event_call = stub.calls[1]
    assert stub.channel.secure is True
    assert venue_call[1].selected_beverage_id == "bev_1"
    assert venue_call[1].lat == 37.5
    assert venue_call[1].budget_mode == pb2.BUDGET_MODE_SOFT
    assert event_call[1].event_type == pb2.RECOMMENDATION_EVENT_TYPE_CLICK
    assert event_call[1].metadata["surface"] == "chatbot"
