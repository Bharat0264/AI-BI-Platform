# Pilot technical rehearsal

Command: `python -m experiments.pilot_rehearsal`

The rehearsal creates an in-memory, explicitly `synthetic_development` package with no human records. The freeze gate returns `NOT_READY` because it requires human-set `external_human` authorship and a real freeze timestamp. It validates the fail-closed path without creating, storing, or representing any synthetic label as human work.

For genuine collection: distribute the private role package, import locked submissions into the restricted package storage, run `python -m benchmark.quality_control PACKAGE`, run `python -m benchmark.freeze PACKAGE`, then only after a human storage freeze execute `python -m experiments.independent_evaluation --package PACKAGE --output RESULTS.json`. Measured comparison reporting must consume only the post-freeze result trace.
