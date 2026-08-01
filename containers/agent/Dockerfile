FROM python:3.11-slim

WORKDIR /app
COPY src/purposebench/prompts.py /app/prompts.py
COPY containers/agent/agent.py /app/agent.py

RUN useradd --create-home --uid 10001 purposebench \
    && mkdir -p /output \
    && chown -R purposebench:purposebench /app /output

USER purposebench
CMD ["python", "/app/agent.py"]
