"""Test skill loading from SKILL.md files following agentskills.io standard."""
import tempfile
from pathlib import Path

from src.skill_loader import SkillLoader


def test_load_skill_parses_frontmatter():
    """Given a valid SKILL.md, load_skill returns a Skill with parsed metadata."""
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: "A test skill"
user-invocable: true
disable-model-invocation: false
allowed-tools:
  - search_vault
  - web_search
---
# Test Skill
Instructions here.
""")

        loader = SkillLoader(Path(tmp))
        skill = loader.load_skill("test-skill")

        assert skill.name == "test-skill"
        assert skill.description == "A test skill"
        assert skill.user_invocable is True
        assert skill.disable_model_invocation is False
        assert skill.allowed_tools == ["search_vault", "web_search"]
        assert "Instructions here." in skill.instructions


def test_load_skill_imports_scripts():
    """Skill scripts/ directory functions are importable."""
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / "test-skill"
        skill_dir.mkdir()
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "__init__.py").write_text("")
        (scripts_dir / "hello.py").write_text("""
def greet(name: str) -> str:
    '''Greet someone by name.'''
    return f"Hello, {name}"
""")
        (skill_dir / "SKILL.md").write_text("""---
name: test-skill
description: "Test"
---
Nothing.
""")

        loader = SkillLoader(Path(tmp))
        skill = loader.load_skill("test-skill")

        assert "greet" in skill.tools
        assert callable(skill.tools["greet"])


def test_load_core_skills():
    """load_core_skills loads all skills from skills/core/."""
    with tempfile.TemporaryDirectory() as tmp:
        core_dir = Path(tmp) / "core"
        core_dir.mkdir(parents=True)
        (core_dir / "SKILL.md").write_text("""---
name: core
description: "Core capabilities"
---
Core instructions.
""")

        loader = SkillLoader(Path(tmp))
        skills = loader.load_core_skills()

        assert len(skills) == 1
        assert skills[0].name == "core"


def test_load_skill_missing_skill_md_raises():
    """Missing SKILL.md raises FileNotFoundError."""
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / "no-file"
        skill_dir.mkdir()

        loader = SkillLoader(Path(tmp))
        import pytest
        with pytest.raises(FileNotFoundError):
            loader.load_skill("no-file")


def test_load_skill_malformed_frontmatter_raises():
    """Malformed YAML frontmatter raises a descriptive error."""
    with tempfile.TemporaryDirectory() as tmp:
        skill_dir = Path(tmp) / "bad-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""---
name: bad
  - invalid: [yaml: broken
---
Content.
""")

        loader = SkillLoader(Path(tmp))
        import pytest
        with pytest.raises(ValueError, match="YAML"):
            loader.load_skill("bad-skill")
