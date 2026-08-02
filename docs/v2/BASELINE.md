# Protocol V2 Local Baseline

The PurposeBound-Fin v2 work is isolated on `research/fin-clean-room-local-v2`. Its clean baseline commit is `2f88824c5fed6d739becdf5a52cc546e37de2589`, created on top of the preserved `protocol-v1.1` commit.

Baseline validation:

- pytest: 8 passed.
- Ruff: passed.
- mypy: passed without incremental cache.

The v1 datasets, manifests, failed/successful smoke streams, pilot stream, cleanup stream, and derived directories were copied to a recoverable external archive. Hashes and archive verification are recorded in `V1_PRESERVATION_MANIFEST.json`.

V2 implementation must use only the namespaced paths listed in that manifest. Existing v1 generators and cleanup paths must not be reused until they accept an explicit v2 destination and reject overwrite.

