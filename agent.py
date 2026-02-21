from pathlib import Path

PROJECTS_DIR = Path("projects")


class ProjectAgent:
    def __init__(self, project_name: str) -> None:
        self.name = project_name
        self.project_dir = PROJECTS_DIR / project_name
        self.ground_truth = self._load_file("ground_truth.txt")
        self.messages = self._load_file("messages.txt")

    def _load_file(self, filename: str) -> str:
        path = self.project_dir / filename
        if path.exists():
            return path.read_text().strip()
        return ""
