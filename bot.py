from slack_bolt import App


def register_handlers(app: App) -> None:
    app.event("app_mention")(handle_app_mention)


def handle_app_mention(event: dict, say) -> None:
    user = event.get("user", "someone")
    say(f"Hello <@{user}>, I heard you! HumanAnd is online.")
