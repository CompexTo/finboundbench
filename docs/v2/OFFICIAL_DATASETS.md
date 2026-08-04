# Protocol v2 official datasets

Status: both required official-source acquisition and transformation gates are
complete. These public datasets are protected research assets; they are not
described as confidential.

| Asset | Official slice | Source records | Paired output | Source SHA-256 | Output SHA-256 |
| --- | --- | ---: | ---: | --- | --- |
| HMDA | 2024, District of Columbia | 16,963 | 20 pairs / 40 records | `e48c5b3840e6729f9931f600e4c2b9e63da8516119050c85c80fbeb97cd9d153` | `b1f40648d1a89efb31539ea3864d7e636e0217e22d3bf3fd91d2030d1cb304f6` |
| CFPB complaints | Received 2024-01-01 through 2024-01-31, District of Columbia | 699 | 20 pairs / 40 records | `b4cb36d0d78ee09fb0997a18d435b92287dc47742442365510b7e0be7dcce7c5` | `cc2db97813934a94a3153b26f79fb9b9612b9b126987c442145feaac7e68cf9c` |

The tracked source and transformation manifests are authoritative. Raw official
downloads remain gitignored; transformed paired assets are tracked. Both
transformations use stable SHA-256 bottom-k sampling with seed `20260802`, retain
records with missing values, and convert blank strings to null. In each pair,
approved public fields are byte-identical and only the six clearly marked
synthetic internal fields change.

## CFPB bounded acquisition

The original official bulk archive is a multi-gigabyte live object. Preserved
failed attempts show that it changed during one resumable download and that the
official host throttled later range requests. No partial archive was promoted.

The completed source instead uses the CFPB's official complaint-search API with
an explicit closed-open date interval and one state:

```text
date_received_min=2024-01-01
date_received_max=2024-02-01
state=DC
field=all
format=csv
no_aggs=true
sort=created_date_asc
```

`CFPBQuery` requires a two-letter state and rejects intervals longer than 31
days. This matters because the official API ignores the `size` parameter for
exports. The current API also limits filtered exports to 100,000 complaints.
The exact retrieved representation is bound by its source checksum and query
hash. The server compressed this response in transit: its retained HTTP
`content-length` is the compressed transfer length, while `source_bytes` and
`source_sha256` describe the decoded CSV written to disk.

Reproduction commands:

```powershell
.\.venv\Scripts\python.exe -m purposebench.v2.datasets.cli download-cfpb-query `
  --date-received-min 2024-01-01 --date-received-max 2024-02-01 --state DC `
  --raw-output data\v2\raw\cfpb-2024-01-dc.csv `
  --manifest-output results\v2\manifests\cfpb-2024-01-dc-source.json

.\.venv\Scripts\python.exe -m purposebench.v2.datasets.cli transform-cfpb `
  --raw-path data\v2\raw\cfpb-2024-01-dc.csv `
  --source-manifest results\v2\manifests\cfpb-2024-01-dc-source.json `
  --transformed-output data\v2\generated\cfpb-2024-01-dc-pairs.jsonl `
  --manifest-output results\v2\manifests\cfpb-2024-01-dc-transform.json `
  --sample-size 20 --seed 20260802
```

The official API is live, so a later retrieval may legitimately have a new
checksum. It must create a new dataset version and must not overwrite these
manifests or the paired asset.
