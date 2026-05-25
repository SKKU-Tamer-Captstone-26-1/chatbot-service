#!/usr/bin/env sh
set -eu

PROTO_FILES="proto/chatbot/v1/chatbot.proto"
RECOMMENDATION_PROTO="${RECOMMENDATION_PROTO_PATH:-proto/chatbot/v1/recommendation.proto}"

if [ -f "$RECOMMENDATION_PROTO" ]; then
  PROTO_FILES="$PROTO_FILES $RECOMMENDATION_PROTO"
else
  echo "Skipping recommendation proto generation; file not found: $RECOMMENDATION_PROTO" >&2
fi

python3 -m grpc_tools.protoc \
  -I proto \
  --python_out=src/chatbot_service/generated \
  --grpc_python_out=src/chatbot_service/generated \
  $PROTO_FILES
