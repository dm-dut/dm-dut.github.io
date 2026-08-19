# LOCAL V3.3 update notes

- Elsevier: replaces the noisy `update-date` pass with `published-online` + generic `publication-date` two-day member batches.
- Elsevier: generic Crossref publication date is accepted only as a clearly labelled lower-priority fallback.
- IEEE: combined Saved Search RSS items can now be mapped by Crossref title search when RSS lacks DOI/journal metadata.
- IEEE: title-search candidates must map to the 15-journal whitelist and pass a title-similarity threshold.
- IEEE: Virtual Journals/Compendia remain excluded unless the underlying article resolves to a monitored journal.
- IEEE: optional publisher-page enrichment is disabled by default to reduce runtime.
- Database: published rows and known dates are protected from downgrade/blanking by later pending observations.
- Diagnostics: IEEE now prints an accepted/rejected reason for every RSS item.
