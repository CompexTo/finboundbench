FROM python@sha256:25976e9d34a0fab1f278cae931f34c8303d97bf0c0d7f85b6b4dcf641d7702a4

WORKDIR /workspace
COPY --chown=65532:65532 gate.py /app/gate.py
RUN mkdir -p /input && chown 65532:65532 /input && chmod 0555 /input
USER 65532:65532
ENTRYPOINT ["python", "/app/gate.py"]
