import pytest

from factory.tools.filesystem import FilesystemTool
from factory.tools.git import GitTool


def test_filesystem_scoped_write_read(tmp_path):
    fs = FilesystemTool(tmp_path)
    fs.write_text("a/b.txt", "hello")
    assert fs.read_text("a/b.txt") == "hello"
    assert fs.exists("a/b.txt")
    assert fs.list_dir("a") == ["b.txt"]


def test_filesystem_blocks_escape(tmp_path):
    fs = FilesystemTool(tmp_path)
    with pytest.raises(PermissionError):
        fs.write_text("../escape.txt", "nope")


def test_git_tool_branch_commit_merge(tmp_path):
    git = GitTool(tmp_path)
    git.init()
    git._run("config", "user.email", "factory@example.com")
    git._run("config", "user.name", "SDLC Factory")

    (tmp_path / "README.md").write_text("base\n")
    git.add("README.md")
    base = git.commit("initial commit")

    git.create_branch("feature/demo")
    (tmp_path / "feature.txt").write_text("feature work\n")
    git.add("feature.txt")
    feature_commit = git.commit("feature commit")
    assert feature_commit != base

    git.checkout("main")
    merge_commit = git.merge("feature/demo", "merge feature/demo")
    assert git.current_branch() == "main"
    assert merge_commit not in (base, feature_commit)
