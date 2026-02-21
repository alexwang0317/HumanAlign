import logging
import os

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from bot import register_handlers


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")
    load_dotenv()
    app = create_app()
    register_handlers(app)
    start_socket_mode(app)


def create_app() -> App:
    return App(token=os.environ["SLACK_BOT_TOKEN"])


def start_socket_mode(app: App) -> None:
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()


if __name__ == "__main__":
    main()
