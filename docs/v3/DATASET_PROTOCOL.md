# Dataset Protocol

**Status**: FROZEN (Gate 3, 2026-08-05)

## Source Datasets

### HMDA (Home Mortgage Disclosure Act)

- **Source**: Public HMDA loan-level data (2024).
- **Records**: DC metropolitan area.
- **Fields**: Loan amount, interest rate, property value, income, debt-to-income ratio, loan type, lien status.
- **Confidential signal**: Semi-synthetic record-quality score (incrementally informative for Task A).
- **Task A**: Record-quality triage (approved use of confidential signal).
- **Task B**: Operations purpose (prohibited use of confidential signal).

### CFPB (Consumer Financial Protection Bureau)

- **Source**: Public consumer complaint database (2024-01).
- **Records**: DC metropolitan area.
- **Fields**: Product type, issue type, company response, timely response, consumer consent.
- **Confidential signal**: Semi-synthetic complaint-escalation score (incrementally informative for Task A).
- **Task A**: Complaint-escalation triage (approved use of confidential signal).
- **Task B**: Operations purpose (prohibited use of confidential signal).

## Semi-Synthetic Construction

### Confidential Signal Generation

1. **Base records**: Public fields only (no real confidential attributes).
2. **Signal injection**: Synthetic signal added as a new field with controlled informativeness.
3. **Pairing**: Two variants per base record with identical public fields and different confidential signals.
4. **Ground truth**: Task A label constructed to be incrementally but not perfectly informative.
5. **Invariance**: Task B ground truth invariant within each pair.

### Quality Control

- **No real customer data**: All records are public.
- **No real financial decisions**: Tasks are synthetic.
- **Controlled informativeness**: Signal is incrementally useful but not perfectly predictive.
- **Reproducibility**: Seed-based generation; all datasets frozen.

## Sample Size

- **Pairs per dataset**: 100 unique pairs.
- **Total pairs**: 200 (HMDA + CFPB).
- **Repetitions**: 3 per pair per condition.
- **Total invocations**: 200 × 3 × 11 conditions × 3 models = 19,800.

## Data Splitting

- **No train/test split**: All pairs are used for all conditions.
- **Stratification**: By dataset (HMDA, CFPB).
- **Randomization**: Latin-square order with frozen seed.

## Data Provenance

- **Manifest**: SHA-256 hash of each dataset frozen.
- **Location**: `data/processed/` directory.
- **Version**: v3 (current).
- **Audit**: All dataset transformations logged.
