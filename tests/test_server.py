from chatbot_service.server import load_generated_chatbot_grpc, normalize_grpc_addr


def test_normalize_grpc_addr_accepts_port_only():
    assert normalize_grpc_addr(":9100") == "[::]:9100"


def test_load_generated_chatbot_grpc_loads_generated_modules():
    generated = load_generated_chatbot_grpc()

    assert generated.chatbot_pb2.DESCRIPTOR.services_by_name["ChatbotService"].full_name == (
        "ontheblock.chatbot.v1.ChatbotService"
    )
    assert hasattr(generated.chatbot_pb2_grpc, "ChatbotServiceServicer")
