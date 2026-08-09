# FinBoundBench

Benchmarking **purpose-selective AI** in financial decision systems.

Financial organizations may be authorized to hold a confidential attribute for
one purpose while being prohibited from using it for another. A
purpose-selective system must do both: preserve the attribute's authorized
utility (it may *use* it) and prevent its cross-purpose influence (it must not
*act on* it). FinBoundBench measures both properties at the decision level,
against a model's own natural-decision floor.

## Highlights

- **Confirmatory evidence (frozen, independently re-verified).** In a
  preregistered study across two model families (DeepSeek V4 Pro; Kimi K3) and
  two financial tasks (hardship-support routing; fraud review):
  - Prohibited-visible data changed decisions on **96–100%** of cases
    (natural-decision floor: 0–4%).
  - Masking the field suppressed influence to **at or below the floor** in
    every condition.
  - Purpose-annotated governed execution retained the **full authorized
    utility gain** (utility-retention ratio 1.0 in both studies).
- **Paper.** "Authorized to Use, Forbidden to Influence: Purpose-Selective AI
  for Financial Decision Systems" — `paper/main.pdf` (anonymous, 6 pp).
- **Competition.** ICAIF 2026 challenge-track proposal + complete starter kit
  (harness, degenerate baselines, sample submission, schema, rules) —
  `competition/`.
- **Reproducible.** `make reproduce` regenerates every statistic, check,
  figure, and PDF from frozen raw events — no API key.

## Quick start

```bash
make reproduce      # full verification + build (no API key)
make test           # unit tests, incl. 9/9 anti-gaming checks
make starter-kit    # regenerate the dev leaderboard
```

See `REPRODUCIBILITY.md` for the exact pipeline, determinism guarantees, and
toolchain requirements.

## Repository layout

| Path | Contents |
| --- | --- |
| `paper/` | Anonymous archival paper (source, compiled PDF, claim registries) |
| `competition/` | ICAIF 2026 proposal + competition starter kit + dev leaderboard |
| `benchmark/` | Frozen protocol, power analysis, gatekeeping, data access |
| `data/` | v4 splits + script to fetch the public source datasets |
| `results/v4/` | Frozen manifests, statistics, findings, evidence, figures |
| `docs/research/` | Research history, audits, secret-scan reports, release plan |
| `scripts/` | Reproduce + verification tooling |
| `src/purposebench/v4/` | Benchmark implementation (v4) |

## Limitations (summary)

Two (model, task) pairs; semi-synthetic signals; no formal guarantees; no
trusted-hardware claims; governed masking is equivalent to deterministic
masking on the tested narrow field (no superiority claim). See the paper's
Limitations section and `docs/research/EXECUTIVE_SUMMARY.md`.

## License

Pending the organizers' choice (see `LICENSE`). Contact the organizers via the
competition proposal contact address.

## Citation

See `CITATION.cff`.
