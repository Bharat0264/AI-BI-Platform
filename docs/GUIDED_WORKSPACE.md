# Guided workspace redesign

Implemented 2 November 2026 after feedback that the site was difficult for a normal user to navigate.

## Delivered changes

- Five primary destinations: Start, My data, Results, Ask a question and Download. All previous feature routes remain available under the collapsed More tools menu. Direct links continue to work; unknown links recover to Start.
- A plain-language start page with upload/sample actions, a ready-file confirmation and next-step cards. Successful imports and sample loading go directly to Results. Import buttons/file selection cannot compete while a load is running.
- Clear no-file states with a link back to Start, rather than empty analytical panels and zero-value business results.
- Results appropriate to the file: supplied financial data keeps the existing charts; general data gets observed file facts and a numeric-column summary derived from the backend profile. IDs, dates and category codes are excluded; rounding and missing-value behavior are disclosed.
- A My data preview and friendly column-meaning labels. Internal role codes stay unchanged; technical inference reasons and match scores are optional details. Removed the old misleading display that summed missing percentages across columns.
- Question examples generated from the loaded file's recognized measure/group columns. Clicking an example fills the question without sending it automatically. The normal path is one question and one submit button; voice, raw calculation evidence and saved definition/history controls are collapsed initially. Remembering a selected meaning opens its confirmation section when needed.
- A download page that explains each output. CSV stays available for general files; financial PDF is marked unavailable with an explanation when requirements are missing. The server report gate remains unchanged.
- Mobile navigation keeps all five main choices visible. Long data tables retain contained scrolling. Focus outlines, existing keyboard submission, accessible labels/statuses, reduced motion and the Help dialog remain available.
- The historical public no-login UI state remains supported for isolated demonstrations, but the current deployment Blueprint uses private authenticated accounts. No analytical engine, database behavior, original source data or numerical evidence calculation was changed in this redesign.

## Verification

Browser regression checks retain the existing interpretation, confirmation, conflict, replay, report, date-scope and account/demo flows. Six new scenarios cover the five-destination empty-state/help path, a real upload-to-results-to-question-to-CSV journey, sample-first onboarding, mobile navigation/unknown links, import failure/busy recovery, and exclusion of identifiers/year codes from the simple summary. Chart rendering and infrastructure are mocked where documented by the existing test fixtures; normal browser DOM interactions and applicable Flask routes are exercised.

Desktop/mobile screenshots were generated from synthetic fixture files and visually inspected. These demonstrate layout, not actual business findings. This is a tested interface redesign, not a real-user usability study or accessibility certification. Hosted rendering is confirmed only after deploying the new commit.

See validation/guided-workspace.json for the final measured suite result and source hashes. See USER_GUIDE.md for plain-language instructions.
