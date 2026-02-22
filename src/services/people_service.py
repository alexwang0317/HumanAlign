import logging
import re
from pathlib import Path

from src.services.dashboard_service import parse_messages_txt

log = logging.getLogger(__name__)

PROJECTS_DIR = Path("projects")


def _extract_role(ground_truth: str, user_id: str) -> str:
    """Extract a user's role line from the Directory section."""
    marker = f"(<@{user_id}>)"
    for line in ground_truth.splitlines():
        if marker in line:
            # Line looks like: * **Name** (<@U123>) — Role description
            parts = line.split("—", 1)
            if len(parts) > 1:
                return parts[1].strip()
            return "(no role set)"
    return "(no role set)"


def _iter_project_files(filename: str):
    """Yield (project_name, file_path) for each project that has the given file."""
    if not PROJECTS_DIR.exists():
        return
    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        path = project_dir / filename
        if path.exists():
            yield project_dir.name, path


def scan_user_projects(user_id: str) -> list[dict]:
    """Find all projects a user appears in and their role in each."""
    results = []
    for project_name, gt_path in _iter_project_files("ground_truth.txt"):
        content = gt_path.read_text()
        if f"<@{user_id}>" in content:
            role = _extract_role(content, user_id)
            results.append({"project": project_name, "role": role})
    return results


def scan_user_activity(user_id: str, limit: int = 10) -> list[dict]:
    """Pull recent message timeline entries involving a user across all projects."""
    all_entries = []
    for project_name, messages_path in _iter_project_files("messages.txt"):
        for entry in parse_messages_txt(messages_path):
            if entry["user"] == user_id:
                entry["project"] = project_name
                all_entries.append(entry)
    all_entries.sort(key=lambda x: x["timestamp"], reverse=True)
    return all_entries[:limit]


def build_person_summary(user_id: str, pending_updates: dict | None = None, pending_nudges: dict | None = None) -> str:
    """Build a formatted summary of a user's roles and activity across all projects."""
    projects = scan_user_projects(user_id)
    activity = scan_user_activity(user_id)
    log.info("Person lookup: %s — %d projects, %d activity entries", user_id, len(projects), len(activity))

    if not projects:
        log.info("Person lookup: %s not found in any project", user_id)
        return f"<@{user_id}> doesn't appear in any project directories."

    lines = [f"*<@{user_id}>*\n"]

    lines.append("*Projects*")
    for p in projects:
        lines.append(f"- *{p['project']}* — {p['role']}")

    if activity:
        lines.append("\n*Recent Activity*")
        for entry in activity:
            link = f"<{entry['permalink']}|link>" if entry.get("permalink") else ""
            lines.append(f"- {entry['timestamp']} | {entry['project']} | {entry['category']} | {entry['summary']} {link}")

    # Check pending items
    pending_count = 0
    if pending_updates:
        for pending in pending_updates.values():
            if pending.get("user") == user_id:
                pending_count += 1
    if pending_nudges:
        for pending in pending_nudges.values():
            if pending.get("user") == user_id:
                pending_count += 1
    if pending_count:
        lines.append(f"\n*Pending*\n- {pending_count} item(s) awaiting review")

    return "\n".join(lines)
