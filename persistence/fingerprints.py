"""Content identities for exact-snapshot definition reuse (no inferred dataset families)."""
from __future__ import annotations

from hashlib import sha256
import pickle


def dataset_digest(name, frame):
    # Preserve float precision, schema, index and row order with bounded temporary
    # allocations. Serialize only: never deserialize untrusted pickle input.
    digest = sha256()
    header = ("aura-dataset-v2", str(name), len(frame), list(frame.columns),
              [str(dtype) for dtype in frame.dtypes])
    payloads = (frame.iloc[start:start + 4096].to_dict(orient="split")
                for start in range(0, len(frame), 4096))
    for logical in _with_header(header, payloads):
        encoded = pickle.dumps(logical, protocol=5)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _with_header(header, payloads):
    yield header
    yield from payloads
