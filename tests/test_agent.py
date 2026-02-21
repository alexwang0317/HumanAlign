import tempfile
from pathlib import Path
from unittest.mock import patch

from agent import ProjectAgent


def test_loads_ground_truth():
    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp, "myproject")
        project_dir.mkdir()
        (project_dir / "ground_truth.txt").write_text("Launch MVP by Friday.")
        (project_dir / "messages.txt").write_text("")
        with patch("agent.PROJECTS_DIR", Path(tmp)):
            agent = ProjectAgent("myproject")
    assert agent.ground_truth == "Launch MVP by Friday."


def test_loads_messages_file():
    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp, "myproject")
        project_dir.mkdir()
        (project_dir / "ground_truth.txt").write_text("")
        (project_dir / "messages.txt").write_text("https://slack.com/archives/C1/p123 - pivot decision")
        with patch("agent.PROJECTS_DIR", Path(tmp)):
            agent = ProjectAgent("myproject")
    assert "pivot decision" in agent.messages


def test_missing_files_return_empty():
    with tempfile.TemporaryDirectory() as tmp:
        with patch("agent.PROJECTS_DIR", Path(tmp)):
            agent = ProjectAgent("nonexistent")
    assert agent.ground_truth == ""
    assert agent.messages == ""
