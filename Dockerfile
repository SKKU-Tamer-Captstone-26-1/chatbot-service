FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

RUN addgroup --system chatbot && adduser --system --ingroup chatbot chatbot

COPY pyproject.toml README.md ./
COPY src ./src
COPY proto ./proto
COPY migrations ./migrations

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e .

USER chatbot

EXPOSE 8080

CMD ["chatbot-service"]
