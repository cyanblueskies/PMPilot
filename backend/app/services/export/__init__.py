"""FR-F4 — report export to richer document formats.

Pure formatting: takes a report's Markdown body and renders it as a Word
document. No LLM, no database — the caller loads the report and passes its
fields in (.claude/rules/architecture.md).
"""

from app.services.export.docx import report_to_docx

__all__ = ["report_to_docx"]
