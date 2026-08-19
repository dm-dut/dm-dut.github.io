# LOCAL_FINAL_V3 update notes

Build: `LOCAL-2026.08.19-V3`

## Main performance changes

- Elsevier no longer queries Crossref journal-by-journal during normal operation.
- The 39 Elsevier journals are grouped under Crossref member `78` (Elsevier BV) and DOI prefix `10.1016`.
- One/few cursor-paged `/members/78/works` requests fetch records created in the two-day window; ISSN/title matching is done locally.
- Crossref `select` limits the response to fields actually used by the monitor.
- The old per-ISSN Crossref path remains only as an emergency fallback.
- Default discovery window is two calendar dates: yesterday..today.
- Pending DOI records are not immediately rechecked in the same run. They are rechecked by DOI after at least 20 hours.
- Springer batch size is increased to 100 records per request and reports page progress and elapsed time.
- IEEE Saved Search RSS now tries Crossref metadata before opening the IEEE article page; publisher pages are fallback only.
- IEEE per-journal Crossref supplementation is disabled by default to avoid unnecessary requests.
- HTTP timeout/retry settings are shortened so one slow endpoint does not stall the daily job for many minutes.
- `update_papers.bat` is scheduler-friendly: it no longer pauses and writes a dated log under `paper_monitor_system/logs/`.

## Workbook changes

`journal_list.xlsx` adds:

- `Crossref Member`
- `Crossref Prefix`
- `Crossref Group`

All 39 Elsevier rows are configured as:

- Mode: `elsevier_member_batch`
- Crossref Member: `78`
- Crossref Prefix: `10.1016`
- Crossref Group: `Elsevier-78`

If a future Elsevier-related journal uses a different Crossref member/prefix, edit only that row; the collector automatically creates a separate batch group.
