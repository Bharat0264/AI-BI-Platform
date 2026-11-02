"""Offline public-release gate. Never imports the app or connects to MongoDB."""
import argparse
import json
from pathlib import Path

BLOCKERS = [
    {'id':'live_identity_configuration', 'reason':'Account authentication and namespace isolation are implemented and tested locally; deployment secrets, cookie/TLS policy and real database permissions must be verified on staging.'},

    {'id':'dependencies', 'reason':'The Python 3.12 environment passes the local dependency audit; the actual staging/deployment image must be audited separately.'},
    {'id':'operations', 'reason':'Production resource limits, concurrent load checks and database backup/restore validation remain unverified.'},
]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',choices=['local','public'],required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    public=args.target=='public'
    report={'target':args.target,'status':'BLOCKED' if public else 'LOCAL_EVALUATION_ONLY',
            'public_release_blockers':BLOCKERS,
            'scope':'Architecture policy gate, not a test runner or security certification. Local startup still requires configured MongoDB.'}
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 2 if public else 0


if __name__=='__main__':
    raise SystemExit(main())
