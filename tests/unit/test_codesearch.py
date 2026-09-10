from factory.knowledge.context.codesearch import CodeSearch


def _tree(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "service.py").write_text(
        "class FeedbackService:\n"
        "    def submit_feedback(self, item):\n"
        "        return save(item)\n"
    )
    (tmp_path / "notes.md").write_text("Retention is 24 months per BR-06.\n")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "skip.py").write_text("def hidden(): pass\n")
    return CodeSearch(tmp_path)


def test_grep_finds_matches_with_locations(tmp_path):
    search = _tree(tmp_path)
    hits = search.grep(r"BR-06")
    assert len(hits) == 1
    assert hits[0].path == "notes.md"
    assert hits[0].line_number == 1


def test_symbols_indexes_python_definitions(tmp_path):
    search = _tree(tmp_path)
    symbols = {h.symbol for h in search.symbols()}
    assert symbols == {"FeedbackService", "submit_feedback"}
    filtered = search.symbols("^submit")
    assert [h.symbol for h in filtered] == ["submit_feedback"]


def test_skip_dirs_are_excluded(tmp_path):
    search = _tree(tmp_path)
    assert search.grep("hidden") == []
