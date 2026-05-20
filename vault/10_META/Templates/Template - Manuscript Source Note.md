---
type: source_note
status: archival
source_type: manuscript
date:                     # ca. date (e.g. "ca. 1475") OR YYYY-MM-DD if certain
title:                    # manuscript title
shelfmark:                # e.g. "Mellon MS 14"
repository:               # holding institution (e.g. "Yale Beinecke Library")
languages:                # ISO codes detected, comma-separated (e.g. "la, it")
scripts:                  # paleographic hand(s) identified
page_count:
folios:                   # e.g. "ff. 1r–46v" if foliation known
people:
  -
places:
  -
works:                    # other works referenced
  -
themes:
  -
substances:               # for alchemical / medical / botanical MSS
  -
influences:               # if author/owner is on the Influences roster
  -
manuscript_dir:           # relative path inside 02_SOURCES/Manuscripts/
illustrations_count:
average_confidence:       # "high" | "medium" | "low" — modal across pages
---

# [ca. YYYY] [Title] — [Shelfmark]

## What this is
[One-sentence description: physical object, repository, language(s), apparent date, approximate scope.]

## Provenance
[What's known about origin, ownership history, repository acquisition. Cite the PDF title page if Yale/Beinecke supplied one. Distinguish established provenance from speculation.]

## Hand(s) and language(s)
[Paleographic identification: scripts, scribal hands (single or multiple), languages. Note code-switching if present.]

## Contents — folio by folio
[Survey of what's on each folio or folio range. Brief — one to three sentences per logical section. Reference page numbers in the transcription set as `[p. N]`.]

- **ff. 1r–3v** — [section description; what's on these folios]
- **ff. 4r–12r** — [...]

## Notable passages
[Pick 3–8 passages worth highlighting. Each block: strict transcription, modernized version, English translation. Cite the page sidecar.]

### [p. N] [Short label for the passage]
**Strict transcription** (source language):
> [diplomatic transcription with abbreviations expanded in (parens), uncertain readings in [brackets]]

**Modernized**:
> [modernized source-language version]

**English translation**:
> [faithful translation]

*[Source: `pages/000N.json`]*

## Illustrations
[Note significant illustrations — diagrams, miniatures, decorated initials, marginalia. Inline-embed the most important ones; reference the rest by folder.]

### [p. N] [What the illustration depicts]
![](../../02_SOURCES/Manuscripts/<Title>/illustrations/000N_a.png)
*[Brief description from sidecar.]*

[Full illustration set: `02_SOURCES/Manuscripts/<Title>/illustrations/`]

## People mentioned
- [[Person Name]] — [context, folio reference]

## Places mentioned
- [[Place]] — [context]

## Works referenced
- [[Title]] — [context]

## Substances / materials / techniques
[For alchemical, medical, botanical, recipe, or technical manuscripts. Use the `substances` and `entities` fields from the page sidecars.]

- [Substance]: [as named in the MS, with modern identification if knowable, folio reference]

## Themes
- [[Theme]] — [how the MS engages it]

## Transcription quality
[Overall: confidence levels per page, sections that needed flagging, hands that were harder to read, illegible regions. Where to look in the sidecars for details.]

## Contradictions / uncertainties
[Things that conflict with **other sources already in this vault** — not with your view of mainstream science or ethics. Per AGENTS.md #4.]

## Pages to update
- [ ] [[Page Name]] — [what to add from this MS]

## Outputs this could fuel
[Bios, memos, essays, project framings.]

## Source
- Manuscript: [title]
- Shelfmark: [e.g. Mellon MS 14]
- Repository: [institution]
- Date: [ca. date]
- Languages: [list]
- PDF: [[02_SOURCES/Manuscripts/<Title>/source.pdf]]
- Per-page transcriptions: `02_SOURCES/Manuscripts/<Title>/pages/`
- Illustrations: `02_SOURCES/Manuscripts/<Title>/illustrations/`
- Pipeline: `tools/manuscript-ingest` + `/manuscript-ingest`
