from unittest.mock import MagicMock

from bot import handle_app_mention, register_handlers


def test_register_handlers_adds_app_mention():
    app = MagicMock()
    register_handlers(app)
    app.event.assert_called_with("app_mention")


def test_handle_app_mention_replies_with_user():
    event = {"user": "U12345"}
    say = MagicMock()
    handle_app_mention(event, say)
    say.assert_called_once_with("Hello <@U12345>, I heard you! HumanAnd is online.")


def test_handle_app_mention_missing_user():
    event = {}
    say = MagicMock()
    handle_app_mention(event, say)
    say.assert_called_once_with("Hello <@someone>, I heard you! HumanAnd is online.")
