# Anonymous-review check

Run immediately before every review PDF build.

- [ ] `paper/` contains no company, product, repository, username, organization,
  cloud account, internal hostname, or identifying grant/acknowledgement.
- [ ] Implementation is named only `PSBE-Runtime`.
- [ ] Self-citations use third person and do not reveal unpublished identity.
- [ ] PDF metadata, embedded file paths, Git-derived timestamps, and image
  metadata are scrubbed.
- [ ] Artifact URLs are anonymous and allowed by the venue, or omitted.
- [ ] Internal mapping and marketing documents are outside the paper build.
- [ ] Author list and affiliations are supplied only in the camera-ready branch.

Automated scans are necessary but insufficient; a human author performs the
final visual and metadata review.
