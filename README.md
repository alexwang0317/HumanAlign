# HumanAnd

AI-powered Slack bot that acts as ambient team coordinator. It listens to channel conversations, keeps the team aligned with their stated goals, routes questions to the right people, and maintains a living "ground truth" document that evolves with the team's decisions.

## Why

Teams lose bandwidth to meta-work: "who handles this?", "didn't we decide X?", "are we still doing Y?". HumanAnd sits in the background of Slack and handles the coordination layer so humans can focus on the actual work.

## Features

### Message Classification

Every channel message is classified by Claude into one of five actions:

- **PASS** — Message is aligned and clear. Bot stays silent (most messages).
- **ROUTE** — Someone needs help. Bot identifies the right person from the team directory and tags them in-thread with context.
- **UPDATE** — A team decision was made. Bot proposes a ground truth change for approval.
- **QUESTION** — Something is vague. Bot asks a gentle follow-up for clarity.
- **MISALIGN** — Someone is going against a recorded team decision. Bot flags it with a warning.

### Living Ground Truth

Each Slack channel maps to a project with a structured `ground_truth.txt`:

```markdown
# Project Ground Truth

## Core Objective
Launch the MVP by Friday with zero new database dependencies.

## Directory & Responsibilities
* **Alex** (<@U111>) — Database & Infrastructure
* **Sarah** (<@U222>) — Frontend & UI

## AI Decision Log
* **2026-02-21:** Team agreed to pivot to MongoDB (approved by <@U111>)
```

The ground truth evolves through conversation:
- Bot detects decisions and proposes changes as diffs
- Team members approve or reject via emoji reactions or text replies ("yes"/"no")
- Approved changes are appended to the AI Decision Log and auto-committed to git
- When the document exceeds 1000 words, the bot compacts it (summarizing older entries while preserving the directory and objective)

### Smart Routing

The Directory section maps people to ownership areas using real Slack user IDs. When someone asks "who handles the database?", the bot matches the question to the right person and tags them in-thread:

> "Hey <@U111>, <@U222> needs help understanding the schema migration. Could you jump in here?"

Richer role descriptions = better routing. Set roles with `@bot role <your responsibilities>`.

### Approval Flow

Ground truth changes and misalignment flags go through a human approval flow:

- React with :white_check_mark: / :thumbsup: to approve, :x: to reject
- Text replies work too: "yes", "yeah", "sure" to approve; "no", "nah" to reject
- After approval, the bot validates that all directory user IDs are still in the channel

### Message Timeline

The bot logs important moments (decisions, blockers, milestones, pivots, escalations) to `messages.txt` with timestamps, user IDs, Slack permalinks, and categories. This powers the dashboard timeline and the bot's own memory when answering questions about what happened.

### Conversation Context

No local history storage. On every message, the bot fetches the last 20 channel messages from Slack and passes them alongside the ground truth as context to Claude. Slack is the storage layer.

### Dashboard

Static site deployed to Cloudflare Pages. Shows:
- Recent misalignment flags with original message, bot's nudge, and team response
- Ground truth change history (what changed, who approved/rejected)
- Per-project stats (total events, acceptance rate)
- Project timeline from `messages.txt` with clickable Slack permalinks
- Daily activity chart (Chart.js)

Deploy with `@bot dashboard` in Slack or manually:
```bash
uv run python dashboard.py export <project_name>
npx wrangler pages deploy ./dashboard
```

### Event Logging

All bot actions are logged to per-project SQLite databases (`events.db`) with: timestamp, event type, user, category, content, permalink, and reaction status. This data feeds the dashboard.

## Bot Commands

| Command | Description |
|---------|-------------|
| `@bot initialize` | Set up ground truth with channel members |
| `@bot role <description>` | Set your role/responsibilities in the directory |
| `@bot dashboard` | Export data and deploy the dashboard |
| `@bot <question>` | Ask anything — bot answers grounded in the ground truth |

## Setup

### 1. Create a Slack App

1. Go to [api.slack.com](https://api.slack.com), create a new app
2. **OAuth & Permissions** — add bot token scopes: `app_mentions:read`, `channels:history`, `channels:read`, `chat:write`, `chat:write.public`, `users:read`, `reactions:read`
3. **Event Subscriptions** — subscribe to bot events: `app_mention`, `message.channels`, `reaction_added`
4. **Socket Mode** — enable it, generate an app-level token with `connections:write` scope
5. Install the app to your workspace

### 2. Configure Environment

```bash
cp .env.example .env
```

Fill in your `.env`:
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run

```bash
uv sync
uv run python main.py
```

No tunnel needed — Socket Mode connects outbound.

## Project Structure

```
HumanAnd/
├── main.py              # Entry point — Socket Mode connection
├── bot.py               # Slack event handlers, approval flow
├── agent.py             # ProjectAgent — one per project, holds all state
├── llm.py               # Claude API calls (classify, respond, compact)
├── history.py           # Fetches last 20 messages from Slack API
├── db.py                # Per-project SQLite event logging
├── dashboard.py         # Export to JSON + deploy to Cloudflare Pages
├── prompts/
│   ├── classify.md      # Message classification (ROUTE/UPDATE/MISALIGN/QUESTION/PASS)
│   ├── respond.md       # @mention responses
│   ├── nudge.md         # Gentle follow-up tone
│   ├── misalign.md      # Misalignment warning tone
│   └── compaction.md    # Ground truth compression
├── projects/
│   └── <project_name>/
│       ├── ground_truth.txt
│       ├── messages.txt
│       └── events.db
└── tests/
```

## Testing

```bash
uv run pytest tests/ -v
```

66 tests covering: agent logic, bot message handling, approval flow (reactions + text), LLM classification, history formatting, database operations, dashboard export, and ground truth compaction.

## Dependencies

- `slack-bolt` — Slack bot framework
- `anthropic` — Claude API client
- `python-dotenv` — Environment variable loading
- Python 3.11+
