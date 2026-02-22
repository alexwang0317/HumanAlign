"""Application configuration loaded from environment variables."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AppConfig:
    slack_bot_token: str
    slack_app_token: str
    anthropic_api_key: str
    github_repo: str | None
    github_token: str | None


def load_config() -> AppConfig:
    slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
    slack_app_token = os.environ.get("SLACK_APP_TOKEN")
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")

    missing = []
    if not slack_bot_token:
        missing.append("SLACK_BOT_TOKEN")
    if not slack_app_token:
        missing.append("SLACK_APP_TOKEN")
    if not anthropic_api_key:
        missing.append("ANTHROPIC_API_KEY")

    if missing:
        names = ", ".join(missing)
        raise RuntimeError(f"Missing required environment variables: {names}")

    return AppConfig(
        slack_bot_token=slack_bot_token or "",
        slack_app_token=slack_app_token or "",
        anthropic_api_key=anthropic_api_key or "",
        github_repo=os.environ.get("GITHUB_REPO"),
        github_token=os.environ.get("GITHUB_TOKEN"),
    )
