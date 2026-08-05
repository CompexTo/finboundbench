# Protocol v3 result namespaces

`raw/` contains append-only execution, attack, privacy, failure, cleanup, and
budget events. `derived/` contains deterministic analyses rebuilt from raw
events. `manifests/` binds protocol, data, models, repositories, environment,
and artifacts. `statistics/` contains preregistered power and final statistical
outputs.

The initial no-cost dry run is labeled `INSTRUMENTATION_ONLY`; its values must
not appear as empirical model/security results in the paper. Confirmatory
directories are created only after the protocol freeze manifest is valid.
