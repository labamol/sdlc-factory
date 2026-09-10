"""Ingest a project workspace into the knowledge store.

Maps factory artifacts to context items with authority levels:
approved decisions are binding; requirements, assumptions and specs are
authoritative; other documents and code are informative.
"""

from pathlib import Path

import yaml

from factory.knowledge.context.chunking import chunk_text
from factory.models.context import ContextItem


def _load_yaml(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text()) or []


def ingest_project(project_dir: Path, *, repo_commit: str = "") -> list[ContextItem]:
    items: list[ContextItem] = []

    for req in _load_yaml(project_dir / "requirements" / "requirements.yaml"):
        items.append(
            ContextItem(
                item_id=f"CTX-{req['req_id']}",
                kind="requirement",
                content=req["statement"],
                source=req.get("source", "requirements.yaml"),
                section=req.get("section", ""),
                authority="authoritative",
                subject=req["req_id"],
                repo_commit=repo_commit,
            )
        )

    for asm in _load_yaml(project_dir / "requirements" / "assumptions.yaml"):
        items.append(
            ContextItem(
                item_id=f"CTX-{asm['asm_id']}",
                kind="assumption",
                content=asm["statement"],
                source="requirements/assumptions.yaml",
                authority="authoritative",
                subject=asm.get("req_id", ""),
                superseded_by="inactive" if asm.get("status") != "ACTIVE" else None,
                repo_commit=repo_commit,
            )
        )

    for dec in _load_yaml(project_dir / "decisions" / "decisions.yaml"):
        items.append(
            ContextItem(
                item_id=f"CTX-{dec['decision_id']}",
                kind="decision",
                content=dec["decision"],
                source=dec.get("source", "decisions.yaml"),
                authority="binding" if dec.get("status") == "APPROVED" else "informative",
                subject=dec.get("requirement") or dec.get("feature") or "",
                supersedes=f"CTX-{dec['supersedes']}" if dec.get("supersedes") else None,
                effective_from=dec.get("effective_from"),
                repo_commit=repo_commit,
            )
        )

    specs_dir = project_dir / "specs"
    if specs_dir.exists():
        for spec_file in sorted(specs_dir.rglob("*.md")):
            feature_id = spec_file.parent.name
            for index, chunk in enumerate(chunk_text(spec_file.read_text()), start=1):
                items.append(
                    ContextItem(
                        item_id=f"CTX-SPEC-{feature_id}-{spec_file.stem}-{index:02d}",
                        kind="spec",
                        content=chunk,
                        source=str(spec_file.relative_to(project_dir)),
                        authority="authoritative",
                        subject=feature_id,
                        repo_commit=repo_commit,
                    )
                )
    return items
