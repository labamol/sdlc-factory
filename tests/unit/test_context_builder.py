from factory.knowledge.context.budget import estimate_tokens, fit_to_budget
from factory.knowledge.context.builder import ContextBuilder, render_pack_md
from factory.knowledge.context.embedding import DeterministicHashEmbedder
from factory.knowledge.context.filtering import (
    detect_conflicts,
    filter_superseded,
    resolve_conflicts,
)
from factory.knowledge.context.store import SqliteKnowledgeStore
from factory.models.context import ContextItem, ScoredItem


def _item(item_id: str, content: str, **kwargs) -> ContextItem:
    defaults = {"kind": "doc", "source": "test.md"}
    defaults.update(kwargs)
    return ContextItem(item_id=item_id, content=content, **defaults)


def test_filter_superseded_excludes_old_versions():
    items = [
        _item("I-1", "old", superseded_by="I-2"),
        _item("I-2", "new", supersedes="I-1"),
        _item("I-3", "unrelated"),
    ]
    current, excluded = filter_superseded(items)
    assert [i.item_id for i in current] == ["I-2", "I-3"]
    assert excluded == ["I-1"]


def test_conflict_detection_and_authority_resolution():
    items = [
        _item("I-1", "Retain 12 months.", kind="decision", subject="BR-06",
              authority="informative"),
        _item("I-2", "Retain 24 months.", kind="decision", subject="BR-06",
              authority="binding"),
    ]
    conflicts = detect_conflicts(items)
    assert len(conflicts) == 1
    assert "I-2" in conflicts[0].resolution
    remaining = resolve_conflicts(items, conflicts)
    assert [i.item_id for i in remaining] == ["I-2"]


def test_equal_authority_conflict_stays_unresolved():
    items = [
        _item("I-1", "Email delivery.", kind="decision", subject="BR-08",
              authority="binding"),
        _item("I-2", "Dashboard delivery.", kind="decision", subject="BR-08",
              authority="binding"),
    ]
    conflicts = detect_conflicts(items)
    assert conflicts[0].resolution == ""
    assert len(resolve_conflicts(items, conflicts)) == 2


def test_budget_admits_binding_first_and_never_exceeds():
    binding = ScoredItem(item=_item("I-1", "b " * 100, authority="binding"), score=0.1)
    big = ScoredItem(item=_item("I-2", "x " * 4000), score=0.9)
    small = ScoredItem(item=_item("I-3", "y " * 100), score=0.5)
    budget = estimate_tokens(binding.item.content) + estimate_tokens(small.item.content)
    selected, used = fit_to_budget([big, small, binding], budget)
    assert {s.item.item_id for s in selected} == {"I-1", "I-3"}
    assert used <= budget


def test_builder_end_to_end_produces_versioned_pack():
    store = SqliteKnowledgeStore(":memory:", DeterministicHashEmbedder())
    store.upsert(
        [
            _item("I-1", "Retain feedback 12 months.", kind="decision", subject="BR-06",
                  authority="binding", superseded_by=None),
            _item("I-2", "Retain feedback 24 months.", kind="decision", subject="BR-06",
                  authority="binding", supersedes="I-1"),
            _item("I-3", "BR-06: Closed feedback must be retained.", kind="requirement",
                  subject="BR-06", authority="authoritative"),
            _item("I-4", "Chunking splits markdown text.", kind="doc"),
        ]
    )
    pack = ContextBuilder(store).build(
        "feedback retention BR-06", feature_id="FEAT-01", repo_commit="abc123",
        budget_tokens=200,
    )
    ids = [s.item.item_id for s in pack.items]
    assert "I-1" not in ids  # superseded excluded
    assert "I-1" in pack.excluded_superseded
    assert "I-2" in ids and "I-3" in ids
    assert pack.used_tokens <= pack.budget_tokens
    assert pack.repo_commit == "abc123"
    rendered = render_pack_md(pack)
    assert pack.pack_id in rendered and "I-2" in rendered
    store.close()
