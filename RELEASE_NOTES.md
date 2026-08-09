# Release Notes — finboundbench-icaif26-v1.0 (2026-08-09)

Release candidate 1 of the FinBoundBench public package, prepared for the
ICAIF 2026 competition track and main track.

## What's in the release

- **FinBoundBench benchmark** — paired, purpose-labeled counterfactual
  evaluation for purpose-selective AI in financial decision systems, with a
  natural-decision floor and a non-gameable leaderboard.
- **Confirmatory evidence (frozen)** — a preregistered study across two model
  families (DeepSeek V4 Pro; Kimi K3) and two financial tasks
  (hardship-support routing; fraud review): prohibited-visible data changed
  96–100% of decisions (floor 0–4%), masking suppressed influence to at or
  below the floor in every condition, and governed execution retained the full
  authorized utility gain (AUR = 1.0 in both studies).
- **Paper** — "Authorized to Use, Forbidden to Influence: Purpose-Selective AI
  for Financial Decision Systems" (anonymous, 6 pp of the 8-page limit).
- **Competition proposal** — "FinBoundBench Challenge: Authorized to Use,
  Forbidden to Influence" (3 pp of the 4-page limit) + the complete starter
  kit teams can build on.
- **Reproducibility** — `make reproduce` regenerates every statistic, check,
  figure, and PDF from frozen raw events with no API key.

## Known limitations (see paper §8 and findings report §9)

- Two (model, task) pairs; semi-synthetic signals; no formal guarantees.
- H4 (purpose-agnostic variant) not testable in the registered design.
- Deterministic masking and governed masking are equivalent (P2 ≈ P3); no
  superiority claim.
- Replication study required seven execution windows (provider instability);
  replication cost not recorded in frozen artifacts.

## Getting started

```bash
make reproduce                    # full verification + build (no API key)
make test                         # unit tests (incl. 9/9 anti-gaming)
make starter-kit                  # regenerate the dev leaderboard
```

See `REPRODUCIBILITY.md` and `docs/research/EXECUTIVE_SUMMARY.md`.

## License

See `LICENSE` (to be added at P9 if an OSI license is selected; the release
is currently offered under the repository's default terms pending the
organizers' choice).
