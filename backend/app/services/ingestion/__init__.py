"""Ingestion: upload -> internal schema.

No FastAPI and no LLM imports here. This is the boundary of the deterministic
track and must be testable without either (.claude/rules/architecture.md).
"""

from app.services.ingestion.loader import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_BYTES,
    MAX_ROWS,
    IngestResult,
    UploadRejected,
    ingest,
)
from app.services.ingestion.mapping import (
    REQUIRED_FIELDS,
    MappingResult,
    MissingRequiredFields,
    map_columns,
    normalise_header,
)

__all__ = [
    "ingest",
    "IngestResult",
    "UploadRejected",
    "ALLOWED_EXTENSIONS",
    "MAX_FILE_BYTES",
    "MAX_ROWS",
    "map_columns",
    "MappingResult",
    "MissingRequiredFields",
    "REQUIRED_FIELDS",
    "normalise_header",
]
