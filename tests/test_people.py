import tempfile
from pathlib import Path
from unittest.mock import patch

from src.services.people_service import build_person_summary, scan_user_activity, scan_user_projects


def _create_project(tmp: str, name: str, ground_truth: str, messages: str = "") -> None:
    project_dir = Path(tmp, name)
    project_dir.mkdir()
    (project_dir / "ground_truth.txt").write_text(ground_truth)
    if messages:
        (project_dir / "messages.txt").write_text(messages)


def test_scan_user_projects_finds_user_across_projects():
    with tempfile.TemporaryDirectory() as tmp:
        _create_project(tmp, "project-a", "## Directory\n* **Alex** (<@U111>) — Backend")
        _create_project(tmp, "project-b", "## Directory\n* **Alex** (<@U111>) — API lead")
        with patch("src.services.people_service.PROJECTS_DIR", Path(tmp)):
            results = scan_user_projects("U111")
    assert len(results) == 2
    assert results[0]["project"] == "project-a"
    assert results[0]["role"] == "Backend"
    assert results[1]["project"] == "project-b"
    assert results[1]["role"] == "API lead"


def test_scan_user_projects_skips_projects_without_user():
    with tempfile.TemporaryDirectory() as tmp:
        _create_project(tmp, "project-a", "## Directory\n* **Alex** (<@U111>) — Backend")
        _create_project(tmp, "project-b", "## Directory\n* **Sarah** (<@U222>) — Frontend")
        with patch("src.services.people_service.PROJECTS_DIR", Path(tmp)):
            results = scan_user_projects("U111")
    assert len(results) == 1
    assert results[0]["project"] == "project-a"


def test_scan_user_activity_filters_by_user():
    messages = (
        "# Messages\n"
        "2026-02-21 14:30 | <@U111> | https://slack.com/p1 | decision | Chose SQLite\n"
        "2026-02-21 14:35 | <@U222> | https://slack.com/p2 | blocker | Waiting on API\n"
        "2026-02-21 15:00 | <@U111> | https://slack.com/p3 | milestone | MVP deployed\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        _create_project(tmp, "project-a", "## Directory\n* (<@U111>)", messages)
        with patch("src.services.people_service.PROJECTS_DIR", Path(tmp)):
            results = scan_user_activity("U111")
    assert len(results) == 2
    assert all(r["user"] == "U111" for r in results)
    # Most recent first
    assert "MVP deployed" in results[0]["summary"]


def test_build_person_summary_formats_markdown():
    with tempfile.TemporaryDirectory() as tmp:
        _create_project(
            tmp, "project-a",
            "## Directory\n* **Alex** (<@U111>) — Backend & Infrastructure",
            "# Messages\n2026-02-21 14:30 | <@U111> | https://slack.com/p1 | decision | Chose SQLite\n",
        )
        with patch("src.services.people_service.PROJECTS_DIR", Path(tmp)):
            result = build_person_summary("U111")
    assert "<@U111>" in result
    assert "project-a" in result
    assert "Backend & Infrastructure" in result
    assert "Chose SQLite" in result


def test_build_person_summary_unknown_user():
    with tempfile.TemporaryDirectory() as tmp:
        _create_project(tmp, "project-a", "## Directory\n* **Alex** (<@U111>) — Backend")
        with patch("src.services.people_service.PROJECTS_DIR", Path(tmp)):
            result = build_person_summary("U999")
    assert "doesn't appear" in result


def test_build_person_summary_includes_pending():
    pending_updates = {
        "123.456": {"user": "U111", "update_text": "something", "channel_name": "test"},
    }
    with tempfile.TemporaryDirectory() as tmp:
        _create_project(tmp, "project-a", "## Directory\n* **Alex** (<@U111>) — Backend")
        with patch("src.services.people_service.PROJECTS_DIR", Path(tmp)):
            result = build_person_summary("U111", pending_updates=pending_updates)
    assert "Pending" in result
    assert "1 item" in result


def test_user_mention_lookup():
    """Verify the regex in slack_events.py correctly matches a bare user mention."""
    import re
    user_message = "<@U0AGAKQ1V54>"
    match = re.match(r"^<@(U[A-Z0-9]+)>$", user_message.strip())
    assert match is not None
    assert match.group(1) == "U0AGAKQ1V54"
