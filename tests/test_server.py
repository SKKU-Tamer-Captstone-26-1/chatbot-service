import pytest

from chatbot_service.server import (
    GeneratedGrpcMissingError,
    load_generated_chatbot_grpc,
    normalize_grpc_addr,
)


def test_normalize_grpc_addr_accepts_port_only():
    assert normalize_grpc_addr(":9100") == "[::]:9100"


def test_load_generated_chatbot_grpc_reports_missing_modules():
    with pytest.raises(GeneratedGrpcMissingError):
        load_generated_chatbot_grpc()
