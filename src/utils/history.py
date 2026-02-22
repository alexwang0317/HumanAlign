def fetch_context(client, channel_id: str) -> str:
    """Fetch last 20 channel messages from Slack, formatted for LLM context.

    No local storage — Slack is the storage layer. This keeps the bot stateless
    and means context is always fresh, even after restarts.
    """
    response = client.conversations_history(channel=channel_id, limit=20)
    messages = response.get("messages", [])

    # Slack returns newest-first; reverse so the LLM sees conversation in chronological order
    messages.reverse()

    lines = []
    for msg in messages:
        # Filter out bot messages to prevent the LLM from referencing its own responses
        if msg.get("bot_id") or msg.get("subtype"):
            continue
        user = msg.get("user", "unknown")
        text = msg.get("text", "")
        if text:
            lines.append(f"<@{user}>: {text}")

    return "\n".join(lines)
