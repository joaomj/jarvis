"""Load skills from skills/ following agentskills.io standard."""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Skill:
    """A loaded skill with parsed frontmatter and callable tools."""
    name: str
    description: str = ""
    user_invocable: bool = True
    disable_model_invocation: bool = False
    allowed_tools: list[str] = field(default_factory=list)
    instructions: str = ""
    tools: dict[str, Any] = field(default_factory=dict)
    skill_dir: Path | None = None


class SkillLoader:
    """Load skills from a skills/ directory."""

    def __init__(self, skills_root: Path) -> None:
        self.root = Path(skills_root)

    def load_skill(self, name: str) -> Skill:
        """Parse SKILL.md YAML frontmatter, importlib scripts/, return Skill."""
        skill_dir = self.root / name
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")

        content = skill_md.read_text()
        frontmatter, instructions = self._parse_frontmatter(content)

        tools: dict[str, Any] = {}
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.is_dir():
            for py_file in sorted(scripts_dir.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                module_tools = self._import_script(py_file)
                tools.update(module_tools)

        return Skill(
            name=frontmatter.get("name", name),
            description=frontmatter.get("description", ""),
            user_invocable=frontmatter.get("user-invocable", True),
            disable_model_invocation=frontmatter.get(
                "disable-model-invocation", False
            ),
            allowed_tools=frontmatter.get("allowed-tools", []),
            instructions=instructions,
            tools=tools,
            skill_dir=skill_dir,
        )

    def load_core_skills(self) -> list[Skill]:
        """Load all skills from skills/core/."""
        core_dir = self.root / "core"
        if not core_dir.is_dir():
            return []
        return [self.load_skill("core")]

    def list_skills(self) -> list[str]:
        """List available skill names."""
        return sorted(
            d.name for d in self.root.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        )

    def _parse_frontmatter(self, content: str) -> tuple[dict[str, Any], str]:
        if not content.startswith("---"):
            return {}, content
        parts = content.split("---", 2)
        if len(parts) < 3:  # noqa: PLR2004
            return {}, content
        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML frontmatter: {e}") from e
        return fm or {}, parts[2].strip()

    def _import_script(self, py_file: Path) -> dict[str, Any]:
        """Import a Python file and return its public callables."""
        module_name = f"skill_script_{py_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec is None or spec.loader is None:
            return {}
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return {
            name: obj
            for name, obj in vars(module).items()
            if not name.startswith("_") and callable(obj)
        }
