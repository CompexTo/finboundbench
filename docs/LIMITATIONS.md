# Limitations

- The mapped Compex runtime enforces field access syntactically against the
  explicit fields detected in predefined Train/Analyze/Serve requests. It does
  not emit lower-level per-value read telemetry.
- Custom SQL field detection is best-effort. This benchmark uses an explicit
  quoted allow-list and rejects wildcard projections, but the platform is not a
  general SQL information-flow monitor.
- `OUTPUT_CONTROL` exists in the platform policy schema but is advisory in the
  inspected implementation. Structured-output and sentinel checks are emitted
  by the research-owned agent running inside Compex and are labelled as such.
- The original v1 arbitrary-execution adapter persists environment metadata and
  therefore still rejects commercial model keys. The protocol-v2 remote
  condition uses the reviewed platform secret-reference adapter instead. Its
  projection is processed by OpenRouter and the selected upstream provider, so
  it is explicitly classified as remote processing rather than local execution.
- Per-request OpenRouter controls require parameter support, deny providers that
  collect data, require zero-data-retention routing, and disable fallbacks.
  These controls reduce retention and substitution risk but do not make remote
  processing equivalent to an offline or hardware-attested local backend.
- The benchmark uses deterministic synthetic records. Results may not transfer
  to real financial distributions, longer conversations, multimodal inputs, or
  production tool chains.
- Sentinel matching detects exact explicit disclosure, not paraphrased semantic
  disclosure. Any secondary LLM judge requires separate validation against
  blinded human annotations.
- Model APIs can remain nondeterministic at temperature zero. Repetitions
  estimate but do not eliminate this source of variation.
- This work measures technical behavior. It does not establish or claim legal
  or regulatory compliance.
