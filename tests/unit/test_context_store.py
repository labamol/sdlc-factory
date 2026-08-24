from factory.knowledge.context.chunking import chunk_text
from factory.knowledge.context.embedding import DeterministicHashEmbedder, cosine
from factory.knowledge.context.store import SqliteKnowledgeStore
from factory.models.context import ContextItem


def _item(item_id: str, content: str, **kwargs) -> ContextItem:
    defaults = {"kind": "doc", "source": "test.md"}
    defaults.update(kwargs)
    return ContextItem(item_id=item_id, content=content, **defaults)


def _store() -> SqliteKnowledgeStore:
    return SqliteKnowledgeStore(":memory:", DeterministicHashEmbedder())


def test_chunking_splits_on_headings_and_is_deterministic():
    text = "# A\n\nalpha\n\n## B\n\nbeta\n\n## C\n\ngamma"
    chunks = chunk_text(text)
    assert len(chunks) == 3
    assert chunk_text(text) == chunks


def test_chunking_respects_max_chars():
    text = "\n\n".join(f"paragraph {i} " + "x" * 200 for i in range(10))
    chunks = chunk_text(text, max_chars=500)
    assert all(len(c) <= 500 for c in chunks)
    assert "".join(chunks).count("paragraph") == 10


def test_embedder_is_deterministic_and_normalized():
    embedder = DeterministicHashEmbedder()
    a = embedder.embed("retention period for feedback")
    assert a == embedder.embed("retention period for feedback")
    assert abs(sum(v * v for v in a) - 1.0) < 1e-9
    similar = cosine(a, embedder.embed("feedback retention period"))
    different = cosine(a, embedder.embed("weekly summary report by email"))
    assert similar > different


def test_exact_search_matches_content_and_subject():
    store = _store()
    store.upsert(
        [
            _item("I-1", "Retention is 24 months.", subject="BR-06"),
            _item("I-2", "Weekly report by email.", subject="BR-08"),
        ]
    )
    assert [i.item_id for i in store.exact_search("Retention")] == ["I-1"]
    assert [i.item_id for i in store.exact_search("BR-08")] == ["I-2"]
    store.close()


def test_vector_search_ranks_similar_content_first():
    store = _store()
    store.upsert(
        [
            _item("I-1", "Feedback retention period is 24 months."),
            _item("I-2", "The parser splits markdown into chunks."),
        ]
    )
    results = store.vector_search("how long is feedback retained")
    assert results[0][0].item_id == "I-1"
    store.close()


def test_upsert_marks_superseded_items():
    store = _store()
    store.upsert(
        [
            _item("I-1", "Retain 12 months.", kind="decision", subject="BR-06"),
            _item(
                "I-2", "Retain 24 months.", kind="decision", subject="BR-06",
                supersedes="I-1",
            ),
        ]
    )
    by_id = {i.item_id: i for i in store.all_items()}
    assert by_id["I-1"].superseded_by == "I-2"
    assert by_id["I-2"].superseded_by is None
    store.close()
