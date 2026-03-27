from pathlib import Path

from app.core.config import get_settings
from app.utils.fs import ensure_dir

settings = get_settings()


class LocalArtifactStorage:
    def __init__(self) -> None:
        self.root = ensure_dir(settings.artifacts_dir)

    def job_dir(self, project_id: str, job_id: str) -> Path:
        return ensure_dir(self.root / project_id / job_id)

    def write_text(self, project_id: str, job_id: str, relative_path: str, content: str) -> str:
        base = self.job_dir(project_id, job_id)
        full_path = ensure_dir(base / Path(relative_path).parent) / Path(relative_path).name
        full_path.write_text(content, encoding="utf-8")
        return str(full_path)

    def write_bytes(self, project_id: str, job_id: str, relative_path: str, content: bytes) -> str:
        base = self.job_dir(project_id, job_id)
        full_path = ensure_dir(base / Path(relative_path).parent) / Path(relative_path).name
        full_path.write_bytes(content)
        return str(full_path)