FROM python:3.11-slim

WORKDIR /app
COPY server.py /app/server.py
COPY ../sample_submission /app/submission

EXPOSE 8000
CMD ["python", "server.py"]
