from __future__ import annotations

import os

import pytest

from awp_rp_runtime_v3.runtime.novel_project_sandbox import NovelProjectSandbox


def test_rejects_absolute_parent_and_protected_write(tmp_path):
    sandbox = NovelProjectSandbox(tmp_path)

    with pytest.raises(ValueError, match="relative"):
        sandbox.resolve_relative(str(tmp_path / "outside.md"))
    with pytest.raises(ValueError, match="escaped"):
        sandbox.resolve_relative("../outside.md")
    with pytest.raises(ValueError, match="protected"):
        sandbox.resolve_relative(".awp/authoring/plans/x.json", write=True)
    with pytest.raises(ValueError, match="protected"):
        sandbox.resolve_relative("novel.db-wal", write=True)


def test_rejects_existing_link_that_escapes_project(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "secret.md").write_text("secret", encoding="utf-8")
    link = tmp_path / "linked"
    try:
        if os.name == "nt":
            link.symlink_to(outside, target_is_directory=True)
        else:
            link.symlink_to(outside)
    except OSError:
        pytest.skip("test account cannot create filesystem links")

    sandbox = NovelProjectSandbox(tmp_path)

    with pytest.raises(ValueError, match="escaped"):
        sandbox.resolve_relative("linked/secret.md")


def test_reads_lists_finds_and_greps_project_text(tmp_path):
    (tmp_path / "guidance").mkdir()
    (tmp_path / "world.md").write_text("旧礼堂\n许妍", encoding="utf-8")
    (tmp_path / "guidance" / "style.txt").write_text(
        "许妍说话简短", encoding="utf-8"
    )
    (tmp_path / "novel.db").write_bytes(b"not text")
    sandbox = NovelProjectSandbox(tmp_path)

    listed = sandbox.execute_read("ls", {"path": "."})
    found = sandbox.execute_read("find", {"pattern": "*.md"})
    matched = sandbox.execute_read(
        "grep", {"pattern": "许妍", "path": ".", "literal": True}
    )
    read = sandbox.execute_read("read", {"path": "world.md"})

    assert "world.md" in listed
    assert "world.md" in found
    assert "world.md:2:许妍" in matched
    assert "guidance/style.txt:1:许妍说话简短" in matched
    assert "1: 旧礼堂" in read
    assert "sha256:" in read
    assert "novel.db" not in matched


def test_read_supports_line_window_and_bounded_results(tmp_path):
    (tmp_path / "outline.md").write_text(
        "\n".join(f"第{index}行" for index in range(1, 11)),
        encoding="utf-8",
    )
    sandbox = NovelProjectSandbox(tmp_path)

    result = sandbox.execute_read(
        "read", {"path": "outline.md", "offset": 3, "limit": 2}
    )

    assert "3: 第3行" in result
    assert "4: 第4行" in result
    assert "5: 第5行" not in result

