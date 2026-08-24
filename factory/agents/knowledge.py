"""Knowledge mining agent.

Owns KNOWLEDGE_MINED: ingests the project workspace into the knowledge
store, builds a versioned context pack for the feature under work, builds
the provenance-aware knowledge graph and records both as evidence.
"""

from pathlib import Path

from factory.agents.base import AgentResult
from factory.knowledge.context.builder import ContextBuilder, render_pack_md, save_pack
from factory.knowledge.context.embedding import DeterministicHashEmbedder
from factory.knowledge.context.store import SqliteKnowledgeStore
from factory.knowledge.graph.ingest import build_project_graph
from factory.knowledge.graph.ontology import NodeType
from factory.knowledge.graph.store import SqliteGraphStore
from factory.knowledge.graph.traversal import impact, lineage
from factory.knowledge.ingestion.project import ingest_project
from factory.models.enums import FactoryState
from factory.models.evidence import Evidence
from factory.models.feature import FeatureState
from factory.orchestrator.events import new_id
from factory.tools.filesystem import FilesystemTool
from factory.tools.git import GitError, GitTool


def _render_graph_report(graph: SqliteGraphStore) -> str:
    node_count, edge_count = graph.counts()
    lines = [
        "# Knowledge Graph",
        "",
        f"- nodes: {node_count}",
        f"- edges: {edge_count}",
        "",
        "## Requirement impact (downstream) and lineage anchors",
        "",
    ]
    for req in graph.nodes_by_type(NodeType.REQUIREMENT):
        downstream = impact(graph, req.node_id)
        lines.append(f"### {req.node_id}: {req.label}")
        lines.append(f"impact ({len(downstream)}): {', '.join(downstream) or 'none'}")
        lines.append("")
    for ac in graph.nodes_by_type(NodeType.ACCEPTANCE_CRITERION)[:3]:
        upstream = lineage(graph, ac.node_id)
        lines.append(f"### lineage of {ac.node_id}")
        lines.append(f"upstream: {', '.join(upstream) or 'none'}")
        lines.append("")
    return "\n".join(lines)


class KnowledgeAgent:
    name = "knowledge-agent"

    def __init__(self, project_dir: Path, *, budget_tokens: int = 4000) -> None:
        self.project_dir = project_dir
        self.fs = FilesystemTool(project_dir)
        self.budget_tokens = budget_tokens

    async def execute(self, feature: FeatureState, stage: FactoryState) -> AgentResult:
        if stage != FactoryState.KNOWLEDGE_MINED:
            return AgentResult(status="FAILURE", summary=f"Unsupported stage {stage.value}")

        repo_commit = ""
        git = GitTool(self.project_dir)
        if git.is_repo():
            try:
                repo_commit = git.current_commit()
            except GitError:
                repo_commit = ""

        items = ingest_project(self.project_dir, repo_commit=repo_commit)
        if not items:
            return AgentResult(status="FAILURE", summary="No project knowledge to ingest")

        store = SqliteKnowledgeStore(
            self.project_dir / "context" / "knowledge.db", DeterministicHashEmbedder()
        )
        try:
            store.upsert(items)
            builder = ContextBuilder(store)
            query = f"{feature.title} {' '.join(feature.requirements)}".strip()
            pack = builder.build(
                query,
                feature_id=feature.feature_id,
                spec_version=feature.spec_version,
                repo_commit=repo_commit,
                budget_tokens=self.budget_tokens,
            )
        finally:
            store.close()

        pack_path = save_pack(pack, self.project_dir / "context" / "packs")
        md_path = self.fs.write_text("specs/context-pack.md", render_pack_md(pack))

        graph = SqliteGraphStore(self.project_dir / "context" / "graph.db")
        try:
            node_count, edge_count = build_project_graph(self.project_dir, graph)
            report = _render_graph_report(graph)
        finally:
            graph.close()
        report_path = self.fs.write_text("specs/knowledge-graph.md", report)

        def evidence(kind: str, ref: str, summary: str) -> Evidence:
            return Evidence(
                evidence_id=new_id("EVD"), stage=stage.value, kind=kind, ref=ref,
                summary=summary, metadata={"pack_id": pack.pack_id},
            )

        return AgentResult(
            summary=(
                f"Ingested {len(items)} items; pack {pack.pack_id} with "
                f"{len(pack.items)} items, {pack.used_tokens}/{pack.budget_tokens} tokens"
            ),
            evidence=[
                evidence("context-pack", str(pack_path), "Versioned context pack"),
                evidence("context-pack-md", str(md_path), "Rendered context pack"),
                evidence(
                    "knowledge-graph", str(report_path),
                    f"Graph: {node_count} nodes, {edge_count} edges",
                ),
            ],
            skill="knowledge/context-pack-building",
        )
