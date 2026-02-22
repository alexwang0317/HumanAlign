import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.handlers import slack_events
from src.stores.db import _connections, get_events


def _reset_state():
    slack_events._agents.clear()
    slack_events._pending_updates.clear()
    slack_events._pending_nudges.clear()
    _connections.clear()


def test_update_flow_approve_reaction_integration():
    _reset_state()
    with tempfile.TemporaryDirectory() as tmp:
        with patch("src.services.project_service.PROJECTS_DIR", Path(tmp)):
            with patch("src.stores.db.PROJECTS_DIR", Path(tmp)):
                with patch("src.handlers.slack_events._resolve_channel_name", return_value="test-channel"):
                    with patch("src.handlers.slack_events.fetch_context", return_value=""):
                        with patch("src.services.project_service.classify_message", return_value="UPDATE|decision: Use SQLite"):
                            with patch("src.services.project_service.ProjectAgent._git_commit", return_value=None):
                                event = {
                                    "channel": "C123",
                                    "user": "U123",
                                    "text": "let's use sqlite",
                                    "ts": "123.456",
                                }
                                say = MagicMock()
                                say.return_value = {"ts": "999.000"}
                                client = MagicMock()

                                slack_events.handle_message(event, client, say)

                                assert "999.000" in slack_events._pending_updates

                                reaction_event = {
                                    "reaction": "white_check_mark",
                                    "user": "U123",
                                    "item": {"ts": "999.000", "channel": "C123"},
                                }
                                client.conversations_members.return_value = {"members": ["U123"]}

                                slack_events.handle_reaction(reaction_event, client, say)

        gt_path = Path(tmp) / "test-channel" / "ground_truth.txt"
        assert "Use SQLite" in gt_path.read_text()

        events = get_events("test-channel")
        assert len(events) == 1
        assert events[0]["event_type"] == "UPDATE"
        assert events[0]["reaction"] == "approved"


def test_question_flow_reaction_updates_event():
    _reset_state()
    with tempfile.TemporaryDirectory() as tmp:
        with patch("src.services.project_service.PROJECTS_DIR", Path(tmp)):
            with patch("src.stores.db.PROJECTS_DIR", Path(tmp)):
                with patch("src.handlers.slack_events._resolve_channel_name", return_value="test-channel"):
                    with patch("src.handlers.slack_events.fetch_context", return_value=""):
                        with patch("src.services.project_service.classify_message", return_value="QUESTION|blocker: clarify scope"):
                            event = {
                                "channel": "C123",
                                "user": "U123",
                                "text": "maybe change approach",
                                "ts": "123.456",
                            }
                            say = MagicMock()
                            say.return_value = {"ts": "777.000"}
                            client = MagicMock()

                            slack_events.handle_message(event, client, say)

                            assert "777.000" in slack_events._pending_nudges

                            reaction_event = {
                                "reaction": "white_check_mark",
                                "user": "U123",
                                "item": {"ts": "777.000", "channel": "C123"},
                            }

                            slack_events.handle_reaction(reaction_event, client, say)

        events = get_events("test-channel")
        assert len(events) == 1
        assert events[0]["event_type"] == "QUESTION"
        assert events[0]["reaction"] == "approved"
