# Public-source acquisition report

Retrieved from official UCI static archives on 2026-11-04. Original archives are retained locally in the git-ignored `benchmark/collection/raw/` directory; the committed [acquisition manifest](../benchmark/collection/acquisition_manifest.json) records their byte-level SHA-256 checksums and inspection outputs. No cleaning or transformation was applied to original archives.

| Source | Archive SHA-256 | Observed rows × columns | Status |
| --- | --- | ---: | --- |
| Online Retail | `f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b` | 541,909 × 8 | Verified archive and Excel inspection |
| Online Shoppers Purchasing Intention | `2972e6184d3ad7beaaa831d9fc2b059dc3ee29df69d1ec593c466a5cd8485d14` | 12,330 × 18 | Verified archive and CSV inspection |
| Bank Marketing (`bank-additional-full.csv`) | `e0bf5f5de5b846e2f18e9d90606637267d46dfa260e0f17bb12e605db5efbeb4` | 41,188 × 21 | Verified nested archive and CSV inspection |

Publisher URLs, CC BY 4.0 assertions, citations, release information, restrictions, and domain suitability are in [the registry](../benchmark/collection/dataset_registry.json). Before any corpus freeze, retrieve again only from those publisher URLs or verify these retained originals against the manifest. Derived annotation snapshots must record their source archive hash, selected rows/columns, and transformation recipe; originals remain immutable.

These verified source archives do not make any case independently human-authored. The annotation candidates are developer-authored design prompts and remain unsuitable as evaluation labels until independently authored, double-annotated, adjudicated, and frozen.
