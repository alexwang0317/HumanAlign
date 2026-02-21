# Creation Plan

# Fundamental Problem
The fundamental premise is that AI shouldn't just be a standalone oracle that humans query for answers, or a machine that just generates content. Instead, AI should act as an ambient, ever-present facilitator or coordinator.

Modern teams lose massive amounts of bandwidth to "meta-work" and context-switching. The AI’s job is to sit in the background of human communication and act as a "cognitive middleware," subtly steering the team to keep them aligned with their Stated Higher Goals. It doesn't do the work for them; it optimizes the environment so humans can focus entirely on problem-solving without drifting off track.

## Vision
A Slack bot that listens to channel messages and responds using an LLM, grounded by a project-specific "ground truth" (the stated goal/context in `projects/new_human_and_model.txt`). The bot keeps conversations aligned with the team's actual objectives.

---

## Phase 1: Skeleton (Get a heartbeat)
Goal: Bot exists, connects to Slack via Socket Mode, and echoes back that it heard you.

- [ ] Set up repo (initial commit, push to GitHub)
- [ ] Install dependencies (`slack-bolt`, `anthropic`, `python-dotenv`)
- [ ] Create Slack app with full OAuth scopes (see Slack Scopes below)
- [ ] Enable Socket Mode in Slack API dashboard, generate `xapp-...` token
- [ ] Write minimal `main.py` + `bot.py` — connects via Socket Mode, responds to @mention with a static acknowledgment
- [ ] **Checkpoint:** @mention the bot in Slack, it responds. Done.

### Slack Scopes

**Bot Token Scopes (OAuth & Permissions):**
- `app_mentions:read` — detect when the bot is @mentioned
- `channels:history` — read messages in public channels
- `channels:read` — list and get info about public channels
- `chat:write` — send messages
- `chat:write.public` — send messages to channels the bot hasn't joined
- `users:read` — look up user profiles (names, titles, bot status)

**Event Subscriptions (subscribe to bot events):**
- `app_mention` — triggers when someone @mentions the bot
- `message.channels` — triggers on every message in public channels the bot is in

## Phase 2: Grounding (Give it memory)
Goal: Bot reads the ground truth file and uses it to detect misalignment and route questions.

- [ ] Upgrade ground truth files from plain text to structured markdown (see Ground Truth Format below)
- [ ] Load the channel's ground truth file and cache its contents in memory
- [ ] Integrate Claude API — bot sends ground truth as system context + user's message as the prompt
- [ ] **Two trigger modes:**
  - **@mention** — bot responds directly with an answer grounded in the ground truth
  - **Passive alignment check** — bot reads every channel message, runs a Haiku classification call to check if the message is unclear or conflicts with ground truth. Only speaks up when something seems off — not aggressively, just when intent is ambiguous or direction seems to drift. Err on the side of staying quiet.
- [ ] Cache alignment classification results to minimize API costs (same ground truth + similar message = skip re-check)
- [ ] Map each Slack channel to a project ground truth file (one project per channel)
- [ ] Store API keys in `.env`, add `.env` to `.gitignore`
- [ ] **Checkpoint:** Ask the bot "what's the team's goal?" via @mention — it answers correctly. Post a message that contradicts the ground truth — bot flags it.

### Ground Truth Format

Ground truth files use structured plaintext with Slack user IDs so the bot can actually ping people. Example `projects/new_human_and_model/ground_truth.txt`:

```markdown
# Project Ground Truth

## Core Objective
Launch the MVP by Friday with zero new database dependencies.

## Directory & Responsibilities
* **Alex** (<@U11111111>) — Database & Infrastructure. Owns schema design, migrations, and deployment pipeline. Go-to for anything backend data.
* **Sarah** (<@U22222222>) — Frontend & UI. Owns React components, design system, and user-facing features. Go-to for anything the user sees.
* **Manager Dan** (<@U33333333>) — Product & Timelines. Owns sprint planning, stakeholder updates, and scope decisions. Go-to for priority calls and deadline questions.

## AI Decision Log
* **2026-02-21:** Team agreed to pivot to MongoDB. (Accepted — proposed by bot after #backend discussion)
```

The **Directory** section is critical — it maps people to ownership areas using their real Slack user IDs (find via profile -> three dots -> "Copy member ID"). Each entry should include:
- Name and Slack user ID (so the bot can ping them)
- Their role/title
- What they own (specific areas of responsibility)
- When to route to them (what kinds of questions they handle)

This is what powers the routing system. The richer the role descriptions, the better the bot can match questions to the right person.

The **AI Decision Log** is where accepted ground truth changes get appended, with timestamps and context.

### Messages Timeline Format

Each project's `messages.txt` is a chronological log of important messages. The bot appends to this file whenever it detects a significant moment — a decision, a blocker, a milestone, a pivot, or an escalation.

Format:
```
YYYY-MM-DD HH:MM | <@user_id> | slack_permalink | category | summary
```

Categories: `decision`, `blocker`, `milestone`, `pivot`, `escalation`

Example:
```
2026-02-21 14:30 | <@U11111111> | https://workspace.slack.com/archives/C1/p123 | decision | Team agreed to drop Redis and use SQLite
2026-02-21 15:45 | <@U22222222> | https://workspace.slack.com/archives/C1/p456 | blocker | Frontend blocked on auth API — no endpoint yet
2026-02-22 09:00 | <@U33333333> | https://workspace.slack.com/archives/C1/p789 | milestone | MVP demo deployed to staging
```

This file is append-only and designed to be visualized later as a project timeline (in the dashboard or exported).

### Ground Truth Size Limit

A hardcoded word limit (e.g., `MAX_GROUND_TRUTH_WORDS = 1000`) lives at the top of `ground_truth.py`. When the file exceeds this limit after an accepted update, the bot runs a compaction step:

1. Send the full ground truth to Claude with a prompt: "Compress this document to stay under {limit} words. Preserve all Directory entries and the Core Objective. Summarize older Decision Log entries into concise bullets. Drop anything redundant."
2. Post the compacted version in Slack for Y/N approval (same flow as any other ground truth update).
3. On acceptance, overwrite the file with the compacted version.

This keeps the ground truth from ballooning into a document nobody reads.

### LLM Action Types

The LLM classifies every message into one of four actions. The system prompt (in `prompts/respond.md`) instructs it to output exactly one:

- **`ROUTE: <@UserID> | summary`** — Someone is asking a question or needs help. The bot identifies the right person from the Directory and tags them in-thread with context. Eliminates the "who do I ask?" problem.
- **`UPDATE: [new ground truth entry]`** — A concrete decision was made in conversation. Bot proposes a ground truth change (goes through the Y/N approval flow in Phase 4).
- **`QUESTION: [clarification]`** — Someone said something vague or ambiguous about a task. Bot asks a gentle follow-up to get clarity.
- **`PASS`** — Nothing to do. Message is aligned, clear, and doesn't need routing.

When the bot receives a `ROUTE:` response, it posts in-thread:
> "Hey <@U11111111>, <@U22222222> needs help understanding the MongoDB pivot. Could you jump in here?"

This keeps the main channel clean and connects the right people without anyone having to dig through a wiki.

## Phase 3: Conversation (Make it useful)
Goal: Bot has context for every message and gives substantive responses.

### Context Window: Fetch from Slack, Don't Store

No local history storage. On every incoming message, call `conversations.history(channel=channel_id, limit=20)` to get the last 20 channel messages. Pass them alongside the ground truth as context to the LLM. Slack is the storage layer — the bot is stateless.

**Why this works:**
- Zero persistence complexity — no SQLite tables, no in-memory dicts, no cache invalidation
- Context is always fresh — no stale data from a previous session
- Survives restarts for free — Slack already has the messages
- `conversations.history` is Tier 3 rate-limited (50+/min), fine for most team channels

**What the LLM receives on every call:**
```
[system] ground truth (from projects/<name>/ground_truth.txt)
[system] last 20 channel messages (from Slack API, newest first)
[user]   the current message
```

This means `history.py` shrinks to a single function that fetches and formats recent messages from Slack into a prompt-ready string. No storage, no grouping logic.

### Directory Enrichment: Responsibilities per Person

After `@bot initialize` creates bare directory entries (name + Slack ID), the bot prompts the channel to fill in responsibilities. Each person should have:
- **What they own** — specific areas of the project (e.g., "Database & Infrastructure", "Frontend & UI")
- **When to route to them** — what kinds of questions they handle (e.g., "Go-to for anything backend data")

**How it works:**
1. After initialize, bot posts: "Directory created with N members. To make routing work well, each person should set their role. Use: `@bot role <your responsibilities>`"
2. `@bot role Database & Infrastructure. Owns schema design, migrations, and deployment.` — bot updates that user's Directory entry in ground_truth.txt
3. Bot shows the proposed change as a diff. React :white_check_mark: or :thumbsup: to accept, :x: to reject. Auto-applies on first new role (no existing role to overwrite); asks for confirmation if modifying an existing role.

Without responsibilities, ROUTE classifications are guesses. With them, the bot can match "who handles the database?" to the right person reliably.

### Tasks

- [ ] Add `@bot role <description>` command — updates the calling user's Directory entry with their responsibilities
- [ ] After initialize, bot prompts the channel to set roles
- [ ] Add `conversations.history` fetch — on every message/mention event, pull the last 20 channel messages and format as context
- [ ] Bot replies in-thread, not flooding the channel
- [ ] Write all system prompts in `prompts/` directory:
  - `respond.md` — @mention responses + action classification (ROUTE/UPDATE/QUESTION/PASS)
  - `alignment_check.md` — passive misalignment detection (Haiku)
  - `nudge.md` — the bot's gentle tone when flagging issues
  - `route.md` — routing template for connecting the right people
  - `relevance.md` — reserved for future use (see below)
  - `compaction.md` — ground truth compression when over word limit
  - `ground_truth_update.md` — proposing ground truth edits
- [ ] **Checkpoint:** Have a multi-turn conversation in a channel. Bot remembers what was said in the last 20 messages without any local storage. Each person has responsibilities listed. Ask "who handles the database?" — bot routes correctly.

### Future: Relevance Detection

Not needed for Phase 3 — the rolling 20-message window gives enough context without grouping. If accuracy becomes a problem later (e.g., bot confuses unrelated topics within the window), add a lightweight relevance filter:

**Option A: Time + Participant Window (start here)**
Messages from the same participants within a 10-minute window are assumed continuous. A gap resets. Simple, free, no API calls.

**Option B: Haiku Classification (upgrade path)**
If Option A is too coarse, fall back to a cheap Haiku call: "Is this message related to the recent conversation?" Only triggered when the time/participant signal is ambiguous.

## Phase 4: Living Ground Truth
Goal: Ground truth evolves based on what's happening in Slack.

- [ ] Bot detects when conversations suggest the team's direction is shifting (new decisions, changed priorities, revised goals)
- [ ] Bot **never overwrites or deletes existing ground truth content** without explicit approval
- [ ] Bot proposes edits by showing a unified diff in Slack — deletions prefixed with `−` (red), additions prefixed with `+` (green), with 1-2 lines of surrounding context so you can see where the change fits. Same UX as Claude Code's file edit previews. Example:
  ```
   ## Core Objective
  − Launch the MVP by Friday.
  + Launch the MVP by Thursday — moved up per stakeholder call.

   ## Directory & Responsibilities
  ```
- [ ] Any user in the channel can react to approve or reject — :white_check_mark: or :thumbsup: counts as acceptance, :x: counts as rejection. Text replies ("Y", "yes", "N", "no") also work as fallback.
- [ ] On acceptance: bot writes the change to the channel's ground truth file and appends a changelog entry to the AI Decision Log (date, what changed, why). Changes can add, modify, or remove content — the diff preview is what protects against accidental loss.
- [ ] On acceptance: bot also auto-commits the changed ground truth file to git with a message like "ground_truth: [summary of change] (approved by <@user>)"
- [ ] Bot appends important messages to `messages.txt` — whenever it detects a decision, blocker, milestone, pivot, or escalation, it logs the timestamp, user, Slack permalink, category, and a one-line summary
- [ ] On rejection: bot acknowledges and moves on
- [ ] Bot re-reads ground truth after every accepted change (no restart needed)
- [ ] When ground truth is updated with Directory changes, validate that all listed Slack user IDs are actually members of the channel (`conversations.members` API). If someone is listed but not in the channel, the bot warns: "Heads up — <@U12345> is listed in the Directory but isn't in this channel."
- [ ] The `ground_truth_update.md` prompt should instruct the LLM to include role details (name, Slack ID, what they own, when to route to them) when proposing Directory additions — not just bare names
- [ ] After each accepted update, check word count against `MAX_GROUND_TRUTH_WORDS` (hardcoded in `ground_truth.py`). If over the limit, trigger compaction — summarize older entries, preserve Directory and Core Objective, propose the compacted version for Y/N approval.
- [ ] **Checkpoint:** Bot notices a goal shift in conversation, proposes a ground truth update, user approves, ground truth file is updated.

## Phase 5: Dashboard (Make it visible)
Goal: Track what the bot is doing so humans can review its behavior over time. Dashboard deployed to Cloudflare Pages as a static site.

### Logging

- [ ] Log every misalignment flag to SQLite — store: timestamp, channel, original message, nudge message, user reaction (approved/rejected/ignored)
- [ ] Add reaction buttons to nudge messages — nudges get the same :white_check_mark:/:x: flow as ground truth updates. :white_check_mark: = "yes, this was off-track", :x: = "no, it's fine". No reaction within the session = "ignored".
- [ ] Log every ground truth update proposal — store: timestamp, channel, proposed change, reason, accepted/rejected, who responded
- [ ] Track pending nudge reactions in `_pending_nudges` (same pattern as `_pending_updates` in bot.py)

### Dashboard (Static Site on Cloudflare Pages)

The dashboard is a static HTML/CSS/JS site. The bot exports its SQLite data to JSON files, then `wrangler pages deploy` pushes the site to Cloudflare Pages. No D1, no API — just a snapshot that gets rebuilt on each deploy.

**Export flow:**
1. `dashboard.py export` — reads SQLite, writes JSON files to `dashboard/data/`:
   - `misalignment.json` — recent flags with nudge + reaction
   - `changes.json` — ground truth update proposals with accept/reject
   - `timeline.json` — parsed `messages.txt` entries across all projects
   - `stats.json` — per-channel counts (nudges, updates, acceptance rate, daily activity)
2. `dashboard/index.html` — static page that reads the JSON and renders everything client-side
3. Deploy: `npx wrangler pages deploy ./dashboard`

**Dashboard shows:**
- [ ] Recent misalignment flags (last 7 days) with the original message, the bot's nudge, and whether the user agreed or pushed back
- [ ] Ground truth change history (what changed, when, why, who approved/rejected)
- [ ] Per-channel stats — total nudges, total updates proposed, acceptance rate
- [ ] Simple timeline bar chart of bot activity per day over the last 7 days (Chart.js, one lightweight dependency)
- [ ] **Project timeline** — visual chronological view of important messages from `messages.txt` (decisions, blockers, milestones, pivots, escalations) with clickable Slack permalinks

**Deploying:**
```bash
# Export latest data from SQLite to JSON
uv run python dashboard.py export

# Deploy to Cloudflare Pages (one-time setup: npx wrangler pages project create humanand-dashboard)
npx wrangler pages deploy ./dashboard
```

- [ ] **Checkpoint:** Run the bot for a day, export data, deploy to Cloudflare Pages. Open the public URL and see a clear picture of what the bot flagged, what changed, and how the team responded.

### SQLite Tables

```
misalignment_log
├── id, timestamp, channel_id
├── original_message       # The message that triggered the flag
├── nudge_message          # What the bot said
└── user_reaction          # "approved", "rejected", or "ignored"

ground_truth_changes
├── id, timestamp, channel_id
├── proposed_change        # What the bot suggested
├── reason                 # Why the bot thought it should change
├── accepted               # Boolean
└── responded_by           # Slack user ID of who reacted
```

## Phase 6: Tests (Prove it works)
Goal: After each module is written, write tests for it. Keep tests focused on behavior.

### `test_llm.py`
- [ ] Given a message that contradicts ground truth, LLM returns a non-PASS action
- [ ] Given a benign message, LLM returns PASS
- [ ] Given a question about ownership, LLM returns ROUTE with the correct user ID from the Directory
- [ ] Given a concrete decision, LLM returns UPDATE with a reasonable entry
- [ ] Given a vague message, LLM returns QUESTION with a clarification

### `test_history.py`
- [ ] Fetches and formats last 20 messages from Slack API response into prompt-ready string
- [ ] Handles empty channel (no messages) gracefully
- [ ] Bot messages are excluded from context (prevent self-reference loops)
- [ ] Messages are ordered oldest-to-newest in the formatted output

### `test_ground_truth.py`
- [ ] Reads and caches a ground truth file correctly
- [ ] After a write, cache is invalidated and re-read returns updated content
- [ ] Compaction triggers when word count exceeds `MAX_GROUND_TRUTH_WORDS`
- [ ] Compaction preserves Directory and Core Objective sections
- [ ] Changelog entry is appended with correct format (date, change, reason)

### `test_db.py`
- [ ] Schema creates tables on first run without error
- [ ] Misalignment log insert and query round-trips correctly
- [ ] Ground truth changes log insert and query round-trips correctly
- [ ] Channel-to-project mapping stores and retrieves correctly

### `test_bot.py`
- [ ] Bot ignores its own messages
- [ ] Bot replies in-thread, not in the main channel
- [ ] Reactions (:white_check_mark:, :thumbsup:) on a pending update are recognized as approval
- [ ] Reaction (:x:) on a pending update is recognized as rejection
- [ ] Text fallback ("Y", "yes", "N", "no") still works for approval/rejection
- [ ] ROUTE action results in a message tagging the correct user

## Phase 7: Polish (Make it solid)
Goal: Handle edge cases, clean up, make it presentable.

- [ ] Error handling (API failures, rate limits, malformed messages)
- [ ] Ignore bot's own messages (prevent loops)
- [ ] Add logging
- [ ] **Checkpoint:** Bot runs reliably for an extended session without crashing.

---

## Repo Structure

```
HumanAnd/
├── main.py                 # Entry point — loads config, starts the Slack bot
├── bot.py                  # Slack event handlers (on_message, threading, approval)
├── llm.py                  # Builds prompts, calls Claude (alignment checks + responses)
├── history.py              # Fetches last 20 channel messages from Slack API, formats as context
├── ground_truth.py         # Reads, caches, and writes ground truth files
├── db.py                   # SQLite setup and queries (history, channel mapping, dashboard logs)
├── dashboard.py            # Serves dashboard view (slash command or local web page)
├── prompts/
│   ├── alignment_check.md  # Prompt for passive misalignment detection (Haiku)
│   ├── nudge.md            # Prompt for how the bot speaks up (gentle tone)
│   ├── respond.md          # Prompt for @mention responses + action classification (ROUTE/UPDATE/QUESTION/PASS)
│   ├── route.md            # Prompt template for routing messages to the right person
│   ├── relevance.md        # Prompt for message relevance classification (Haiku)
│   ├── compaction.md       # Prompt for compressing ground truth when it exceeds word limit
│   └── ground_truth_update.md  # Prompt for proposing ground truth edits
├── agent.py                # ProjectAgent coordinator — one per project, holds all state
├── projects/
│   └── new_human_and_model/        # One folder per project
│       ├── ground_truth.txt        # Goals, directory, decisions (evolves over time)
│       └── messages.txt            # Timeline of important messages (decisions, blockers, milestones)
├── tests/
│   ├── test_llm.py         # Tests for action classification (ROUTE/UPDATE/QUESTION/PASS)
│   ├── test_bot.py         # Tests for message handling, threading, approval parsing
│   ├── test_history.py     # Tests for thread history and relevance detection
│   ├── test_ground_truth.py # Tests for reading, writing, compaction
│   └── test_db.py          # Tests for SQLite queries and schema
├── humanand.db             # SQLite database (auto-created, gitignored)
├── pyproject.toml
├── .env                    # SLACK_BOT_TOKEN, SLACK_APP_TOKEN, ANTHROPIC_API_KEY
├── .gitignore
├── CLAUDE.md
├── plan.md
└── README.md
```

**What each file does:**

- **`main.py`** — Wires everything together. Loads `.env`, initializes the Slack app in Socket Mode, registers handlers from `bot.py`, starts listening. The only file you run.
- **`bot.py`** — Owns all Slack interaction. Handles @mentions, passive message listening, in-thread replies, and Y/N approval flow for ground truth updates.
- **`llm.py`** — Owns all Claude API calls. Loads prompt templates from `prompts/`, builds the full prompt with ground truth + history, routes to the right model (Haiku for cheap classification, Sonnet/Opus for substantive responses).
- **`history.py`** — Single function: calls `conversations.history(limit=20)` on the Slack API and formats the messages into a prompt-ready string. No local storage — Slack is the storage layer.
- **`ground_truth.py`** — Reads and caches ground truth from `projects/`. Writes accepted updates back to the file with changelog entries. Uses channel-project mapping from SQLite.
- **`db.py`** — SQLite setup. Stores thread history, channel-to-project mapping, misalignment log, and ground truth changelog.
- **`dashboard.py`** — Reads from SQLite and serves a dashboard view — recent flags, ground truth history, per-channel stats. Exposed via slash command or a simple local web page.
- **`agent.py`** — `ProjectAgent` class. One coordinator object per project that holds all state: ground truth, messages, history, config. All bot logic for a project flows through this object.
- **`prompts/`** — Markdown files, one per prompt type. Loaded by `llm.py` at call time so you can edit them without restarting. Includes `nudge.md` which defines the bot's gentle tone when flagging misalignment.
- **`projects/`** — One subfolder per project. Each contains `ground_truth.txt` (goals, directory, decisions) and `messages.txt` (chronological timeline of important messages — decisions, blockers, milestones, pivots, escalations — with timestamps, user IDs, and Slack permalinks for deep-linking and later visualization).

## Environment Variables

The `.env` file needs these keys:

```
SLACK_BOT_TOKEN=xoxb-...        # From Slack app OAuth & Permissions
SLACK_APP_TOKEN=xapp-...        # From Slack app Socket Mode settings
ANTHROPIC_API_KEY=sk-ant-...     # From Anthropic console
```

## Dependencies

Add to `pyproject.toml`:

```
slack-bolt          # Slack bot framework
python-dotenv       # Load .env file
anthropic           # Claude API client
```

SQLite is used for persistence (stdlib `sqlite3` — no extra dependency needed).

## How to Run

```bash
# 1. Install dependencies
uv sync

# 2. Run the bot (Socket Mode — no tunnel needed)
uv run python main.py
```

---

## Stretch Goals

### Integration with External Tools
- **Linear** — Same pattern as the GitHub PR monitor. Webhook fires on issue create/update, bot checks the ticket against ground truth, nudges if the ticket conflicts with agreed-upon goals or priorities. Linear's GraphQL API and simple API key auth make this the easiest integration to add.
- **Jira** — Same as Linear but heavier API. Bot reads ticket status and links conversations back to specific issues. When someone asks "what's the status of X?", the bot checks Jira instead of guessing.
- **GitHub** — Surface open PRs, blockers, or recent merges relevant to the current conversation.
- **Google Docs / Notion** — Pull in living documents as additional ground truth beyond the local `projects/` files.

### Relationship Graph + Task Assignment
- **People graph** — Track who works with whom, who owns what areas, and who's blocked on who. Built from Slack message patterns and explicit declarations.
- **Task assignment** — Bot can assign or suggest owners for action items that come up in conversation, based on the relationship graph and past ownership.
- **Workload awareness** — Before suggesting someone for a task, the bot considers what they're already committed to.

### Per-Person Agents + Human-to-Project Directory

The current structure is project-centric: each project has a `ground_truth.txt` that lists people. This stretch goal inverts that — a root-level **people directory** that maps each person to every project they're on, giving each person their own agent context.

**Root-level directory structure:**
```
HumanAnd/
├── people/
│   ├── directory.txt              # Master human-to-project mapping
│   ├── alex/
│   │   └── context.txt            # Alex's cross-project view: all active projects, roles, current blockers
│   └── sarah/
│       └── context.txt
├── projects/
│   └── new_human_and_model/
│       ├── ground_truth.txt       # Project → people (existing, unchanged)
│       └── messages.txt
```

**`people/directory.txt`** — the reverse index:
```
# People Directory

## Alex (<@U11111111>)
- new_human_and_model — Database & Infrastructure
- mobile_app — Backend API lead
- Active blockers: waiting on staging deploy (new_human_and_model)

## Sarah (<@U22222222>)
- new_human_and_model — Frontend & UI
- Active blockers: none
```

**What this enables:**
- **Per-person agent** — When Alex DMs the bot or gets @mentioned, the bot loads Alex's `context.txt` instead of a single project's ground truth. It knows all of Alex's projects, roles, and current state across the org.
- **Cross-project awareness** — The bot can answer "what's on my plate?" by aggregating across all projects a person is assigned to, rather than being siloed to one channel.
- **Automatic sync** — When a project's `ground_truth.txt` Directory section changes (someone added/removed), the people directory updates to match. The project ground truth remains the source of truth; the people directory is a derived view.
- **Workload routing** — Before routing a question to someone, the bot checks their cross-project load. If Alex is listed as blocked on three projects, maybe the question goes to someone else.
- **Personal daily digest** — The bot DMs each person a summary of what happened across all their projects overnight — decisions made, blockers raised, things that need their attention.

### GitHub PR Alignment Monitor

Bot watches PRs and checks if the work matches the author's role in the Directory. Simple ownership check — is a backend engineer submitting frontend code?

**How it works:**
1. **GitHub webhook** — fires on PR opened. Bot receives the PR title, commit messages, and author.
2. **Look up the author** — map GitHub username to a Directory entry in `ground_truth.txt` to get their ownership area.
3. **One Sonnet call** — send the commit messages + the author's ownership area. Prompt: "This person owns [area]. Based on these commit messages, does this PR match their role? PASS or NUDGE + one-line reason."
4. **PASS** — do nothing.
5. **NUDGE** — post to Slack:
   > "Alex opened PR #42 `Redesign navbar component` — Alex owns Database & Infrastructure. Should this go to Sarah (Frontend & UI)?"

**Implementation:**
- GitHub webhook endpoint (or poll with `gh api repos/{owner}/{repo}/pulls`)
- `GITHUB_TOKEN` in `.env`
- GitHub-to-Slack user mapping in Directory (add `github: username` per person)
- One new file: `github_monitor.py`

### Weekly Retrospective & Recommendations

At end-of-week (configurable — default Friday 4pm), the bot generates a per-project summary and posts it to the project channel. It reads from all available context: ground truth, `messages.txt` timeline, misalignment log, GitHub commits (if enabled), and thread history from the week.

**The weekly post includes:**
- **What happened** — key decisions, milestones hit, pivots made (pulled from `messages.txt`)
- **What drifted** — misalignment flags that came up during the week, whether they were resolved or ignored
- **Who did what** — per-person activity summary based on Slack messages and GitHub commits (if enabled), mapped against their stated ownership areas
- **Unresolved blockers** — anything flagged as a blocker in `messages.txt` that never got a corresponding milestone or decision resolving it
- **Recommendations** — the bot's actual suggestions for next week, grounded in the ground truth:
  - Ownership gaps that surfaced (e.g., "Three commits landed in `auth/` this week but nobody owns auth in the Directory — consider assigning it")
  - Ground truth staleness (e.g., "The Core Objective still says 'launch by Friday' but that date passed — update needed?")
  - Workload imbalance (e.g., "Alex was tagged in 14 threads this week, Sarah in 2 — worth redistributing?")
  - Carry-over items (e.g., "Frontend auth blocker from Tuesday is still open")

**Implementation:**
- Scheduled via a simple timer in `main.py` (or cron if running as a service)
- One Sonnet/Opus call per project — send the week's `messages.txt` entries, ground truth, and misalignment log as context with a `prompts/weekly_retro.md` prompt
- Posts as a single formatted Slack message in the project channel
- If per-person agents are enabled, also DMs each person their individual cross-project summary

### Cloudflare Pages Dashboard + D1 Sync

The bot keeps local SQLite as its primary database (fast, zero-latency for the hot path). A background sync layer pushes data to Cloudflare D1 so the dashboard can be deployed publicly on Cloudflare Pages.

**Architecture:**
```
Bot (Python, local)                    Cloudflare
┌──────────────────┐                  ┌──────────────────┐
│ SQLite (primary)  │──sync on write──→│ D1 (read replica) │
│ fast, local       │  or on schedule  │ serverless SQLite  │
└──────────────────┘                  └────────┬──────────┘
                                               │ reads directly
                                      ┌────────▼──────────┐
                                      │ Pages + Functions   │
                                      │ Dashboard (TS)      │
                                      │ publicly accessible  │
                                      └─────────────────────┘
```

**How sync works:**
- On every SQLite write (misalignment log, ground truth change, message timeline entry), the bot fires an async HTTP call to D1's API to replicate the row
- If the network call fails, it queues and retries — local SQLite is always the source of truth, D1 is eventually consistent
- Alternatively, a simpler v1: cron job that bulk-syncs new rows every N minutes

**Dashboard (TypeScript on Cloudflare Pages):**
- Pages Functions read directly from D1 via Worker bindings — no API proxy needed
- Static frontend (HTML/CSS/JS or lightweight framework) shows the same views as Phase 5: misalignment flags, ground truth history, project timeline
- Secrets (Slack tokens for permalink generation, etc.) stored in Cloudflare Pages admin

**Why this split works:**
- Bot stays fast — no network dependency on the critical path
- Dashboard is always on, publicly accessible, doesn't require access to the bot's machine
- D1 is free-tier friendly and uses the same SQLite schema — no migration needed
- If D1 is down, the bot is unaffected

### Git Bisect for Alignment Archaeology

Since Phase 4 auto-commits every ground truth change, `git bisect` can binary-search the commit history to pinpoint exactly when alignment drifted — useful if the decision log grows too large to scan by eye.

---

## Setup Instructions

**The Repository:** Clone this repo. Copy `.env.example` to `.env` and fill in the keys. Run `uv sync`.

**The Slack App:**
1. Go to api.slack.com, create a new app from scratch.
2. **OAuth & Permissions** — add bot token scopes: `app_mentions:read`, `channels:history`, `channels:read`, `chat:write`, `chat:write.public`.
3. **Event Subscriptions** — subscribe to bot events: `app_mention`, `message.channels`.
4. **Socket Mode** — toggle it on. Generate an app-level token with `connections:write` scope. This is your `xapp-...` token.
5. Install the app to your workspace. Copy the Bot User OAuth Token (`xoxb-...`).
6. Add both tokens + your Anthropic API key to `.env`.

**Run it:** `uv run python main.py`. No tunnel needed — Socket Mode connects outbound.
