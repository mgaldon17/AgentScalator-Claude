"""Lesson Markdown mirror — write each lesson to a project directory as ``<id>.md``.

A human-readable, git-versionable copy of every lesson alongside the vector store. When
``lessons.md_dir`` is set, each lesson write also renders a Markdown file (YAML frontmatter
+ the procedure text) into that directory (relative paths resolve against the repo root).
Additive and best-effort — the vector store stays the source of truth; a file error never
breaks a tool.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .atomicio import atomic_write_text
from .config import _REPO_ROOT, Config
from .lesson import Lesson

_log = logging.getLogger("agentmem.mdsink")


def _yaml_scalar(value: str) -> str:
    """Quote a string for a YAML frontmatter scalar (double-quoted, escaped)."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def lesson_to_markdown(lesson: Lesson) -> str:
    """Render a lesson as Markdown: YAML frontmatter (the metadata) + title + procedure."""
    lines = [
        "---",
        f"id: {_yaml_scalar(lesson.lesson_id)}",
        f"title: {_yaml_scalar(lesson.title)}",
        f"origin: {_yaml_scalar(str(lesson.origin))}",
        f"reuse: {lesson.reuse}",
        f"failure_count: {lesson.failure_count}",
        f"pending_review: {str(lesson.pending_review).lower()}",
        "---",
        "",
        f"# {lesson.title}".rstrip(),
        "",
        lesson.content.strip(),
        "",
    ]
    return "\n".join(lines)


class LessonMdDir:
    """Writes/deletes ``<id>.md`` lesson files in the configured project directory."""

    def __init__(self, cfg: Config) -> None:
        d = Path(cfg.lessons_md_dir)
        self._dir = d if d.is_absolute() else _REPO_ROOT / d

    def write(self, lesson: Lesson) -> Path:
        """Write (create-or-replace, atomically) the lesson as ``<id>.md``. Returns the path."""
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{lesson.lesson_id}.md"
        atomic_write_text(path, lesson_to_markdown(lesson))
        _log.info("mirrored lesson %s -> %s", lesson.lesson_id, path)
        return path

    def delete(self, lesson_id: str) -> None:
        """Delete the lesson's ``.md`` (no-op if it is already gone)."""
        (self._dir / f"{lesson_id}.md").unlink(missing_ok=True)


def build_md_sink(cfg: Config) -> LessonMdDir | None:
    """Return a sink when ``lessons.md_dir`` is set, else ``None`` (mirroring off)."""
    return LessonMdDir(cfg) if cfg.lessons_md_dir.strip() else None
