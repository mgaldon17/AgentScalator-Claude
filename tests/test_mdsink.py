"""Tests for the lesson .md directory mirror — Markdown render + real (temp-dir) file I/O."""

from __future__ import annotations

from pathlib import Path

from agentmem.config import Config
from agentmem.lesson import Lesson
from agentmem.mdsink import LessonMdDir, build_md_sink, lesson_to_markdown


def _lesson() -> Lesson:
    l = Lesson.learned(title='Restart the "web" service', content="1. ssh in\n2. systemctl restart web")
    l.lesson_id = "abc123"
    l.reuse = 2
    return l


def test_markdown_has_frontmatter_and_body():
    md = lesson_to_markdown(_lesson())
    assert md.startswith("---\n")
    assert 'id: "abc123"' in md
    assert 'title: "Restart the \\"web\\" service"' in md   # quote escaped in the YAML scalar
    assert "reuse: 2" in md
    assert "pending_review: true" in md
    assert "systemctl restart web" in md
    assert md.count("---") == 2


def test_build_md_sink_off_when_dir_empty():
    cfg = Config()
    cfg.lessons_md_dir = ""
    assert build_md_sink(cfg) is None


def test_write_and_delete_roundtrip(tmp_path: Path):
    cfg = Config()
    cfg.lessons_md_dir = str(tmp_path / "lessons")
    sink = LessonMdDir(cfg)

    path = sink.write(_lesson())
    assert path.name == "abc123.md"
    assert path.exists()
    assert "systemctl restart web" in path.read_text(encoding="utf-8")

    sink.delete("abc123")
    assert not path.exists()
    sink.delete("abc123")  # idempotent — no error on missing file


def test_absolute_dir_is_used_as_is(tmp_path: Path):
    cfg = Config()
    cfg.lessons_md_dir = str(tmp_path)
    sink = LessonMdDir(cfg)
    path = sink.write(_lesson())
    assert path.parent == tmp_path
