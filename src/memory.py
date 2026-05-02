"""Memory management: SOUL.md, MEMORY.md, USER.md with bounded limits."""
from __future__ import annotations

from pathlib import Path


class MemoryManager:
    SOUL_MAX_CHARS = 500
    MEMORY_MAX_CHARS = 2200
    USER_MAX_CHARS = 1375

    def __init__(self, root_dir: Path) -> None:
        self.root = Path(root_dir)

    def get_context(self) -> str:
        parts = []
        soul = self.read_soul_md()
        if soul:
            parts.append(soul)
        memory = self.read_memory_md()
        if memory:
            parts.append(f"[Memory]\n{memory}")
        user = self.read_user_md()
        if user:
            parts.append(f"[User Profile]\n{user}")
        return "\n\n".join(parts)

    def read_soul_md(self) -> str:
        path = self.root / "SOUL.md"
        if not path.exists():
            return ""
        return path.read_text().strip()

    def read_memory_md(self) -> str:
        path = self.root / "MEMORY.md"
        if not path.exists():
            return ""
        return path.read_text().strip()

    def read_user_md(self) -> str:
        path = self.root / "USER.md"
        if not path.exists():
            return ""
        return path.read_text().strip()

    def update_memory(self, facts: str) -> None:
        path = self.root / "MEMORY.md"
        current = self.read_memory_md()
        entry = f"\n- {facts.strip()}"
        updated = current + entry
        while len(updated) > self.MEMORY_MAX_CHARS:
            idx = updated.find("\n", 1)
            if idx == -1:
                updated = updated[-self.MEMORY_MAX_CHARS:]
                break
            updated = updated[idx:]
        path.write_text(updated.strip())

    def update_user_profile(self, key: str, value: str) -> None:
        path = self.root / "USER.md"
        current = self.read_user_md()
        line = f"{key}: {value}"
        new_content = current.rstrip() + "\n" + line if current else line
        if len(new_content) > self.USER_MAX_CHARS:
            while len(new_content) > self.USER_MAX_CHARS:
                idx = new_content.find("\n") + 1
                if idx == 0:
                    break
                new_content = new_content[idx:]
        path.write_text(new_content.strip())
