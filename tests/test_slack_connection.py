"""Integration test — requires real Slack tokens in .env and network access."""

import os

import pytest
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")


@pytest.fixture
def client():
    if not BOT_TOKEN:
        pytest.skip("SLACK_BOT_TOKEN not set")
    return WebClient(token=BOT_TOKEN)


def test_bot_can_authenticate(client):
    response = client.auth_test()
    assert response["ok"]
    print(f"Authenticated as: {response['user']}")


def test_bot_can_post_message(client):
    channels = client.conversations_list(types="public_channel", limit=1)
    assert channels["ok"]
    assert len(channels["channels"]) > 0

    channel_id = channels["channels"][0]["id"]
    channel_name = channels["channels"][0]["name"]

    response = client.chat_postMessage(
        channel=channel_id,
        text="HumanAnd test message — if you see this, the bot is working.",
    )
    assert response["ok"]
    print(f"Posted test message to #{channel_name}")
