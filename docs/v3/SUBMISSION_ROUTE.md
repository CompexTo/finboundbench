# Submission route

Verified: 2026-08-05, Europe/Rome  
Rule: official venue pages override the older local snapshot in
`docs/ICAIF_RULEBOOK.md`.

## Current ICAIF 2026 status

The [official dates page](https://icaif2026.org/important-dates.html) and
[official call for papers](https://icaif2026.org/call-for-papers.html) now show
an extended main-paper deadline of **2026-08-09, 23:59 AoE**, replacing the
original 2026-08-02 date. The main track is therefore technically open as of
this verification.

The main paper must:

- connect AI and finance and be submitted through CMT;
- use the latest ACM `sigconf` format with anonymous review settings;
- fit within eight pages **in total**, including figures and references;
- be a self-contained PDF with no supplementary material or appendix;
- preserve double blindness; there is no rebuttal period;
- use a final author list at initial submission; and
- not be simultaneously under review at another archival venue.

Accepted papers are archival ACM proceedings papers and require an in-person
presentation in Milan. The topic list explicitly includes trustworthy AI,
security/privacy, AI governance, financial workflows, and benchmark
construction, so the subject is in scope.

## Gate decision

**Do not rush a main-track submission by 9 August.** The frozen v2 evidence is
a bounded diagnostic pilot with model/provider failures, four-pair condition
comparisons, no preregistered Task A utility test, and no full v3 attack matrix.
Converting it into a confirmatory result would require fabrication or
post-hoc overclaiming. The eight-page/no-supplement constraint also makes an
unfinished evidence story especially fragile.

Keep the anonymous ACM eight-page scaffold as a discipline and venue-portable
short-paper version. Re-evaluate ICAIF only if all v3 confirmatory gates finish
before the deadline with enough time for human coauthor review; no execution
plan assumes that outcome.

## ICAIF workshop path

The [workshop call](https://icaif2026.org/call-for-workshop-proposals.html)
states:

- workshop proposals closed on 2026-07-19;
- individual workshop paper deadlines are set by accepted workshops and remain
  TBD on the official page;
- workshop notifications are planned for 2026-10-14; and
- workshop papers are non-archival and are not included in the ACM ICAIF
  proceedings.

Action: monitor the official list of accepted workshops and their calls. A
non-archival workshop paper is a suitable route for a protocol, benchmark
design, or preliminary negative result without blocking a later archival
submission. Do not infer a paper deadline until an accepted workshop publishes
one.

## Alternative archival routes

### Recommended if the runtime-security contribution survives: USENIX Security 2027, Cycle 2

The [official preliminary call](https://www.usenix.org/conference/usenixsecurity27/call-for-papers)
lists Cycle 2 registration on **2027-01-19 AoE** and submission on
**2027-01-26 AoE**. It allows 13 pages of body text plus references/appendices
and requires an Open Science appendix. The study must foreground a systems
security contribution, adversarial evaluation, and reproducibility rather than
only an ML benchmark. This is the most realistic current target.

Cycle 1 registration (2026-08-18) and submission (2026-08-25) are too close for
a responsible full study unless the empirical gates unexpectedly complete.

### Conditional systems route: OSDI 2027

The [OSDI 2027 call](https://www.usenix.org/conference/osdi27/call-for-papers)
lists an abstract deadline of 2026-12-01 and paper deadline of 2026-12-08. Use
this route only if PSBE-Runtime becomes a substantive systems contribution with
multi-backend evaluation, end-to-end integration, and strong performance and
failure analysis. A benchmark-only result is not enough.

### Not selected now: NDSS 2027 fall cycle

The [NDSS 2027 call](https://www.ndss-symposium.org/ndss2027/submissions/call-for-papers/)
places the fall paper deadline in August 2026. It is too close to complete and
review the current protocol responsibly.

## Submission checklist retained for every route

- Confirm venue dates again from official pages immediately before any account
  registration or submission.
- Obtain explicit human approval for author list, conflicts, ethics language,
  artifact release, and the final PDF.
- Run the anonymity scan; remove product/company names, repository identifiers,
  acknowledgements, and deanonymizing URLs from the review version.
- Freeze raw data, manifests, analysis environment, and deviations before any
  final prose claim.
- Check concurrent-submission and preprint rules for the selected venue.
- Never submit automatically; submission is an external authorship decision.
