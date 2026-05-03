"""Model registry for OpenCode Go and other providers.

To add a new model: append an entry to AVAILABLE_MODELS.
The Telegram /model menu auto-generates from this list.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelEntry:
    id: str           # PydanticAI format: "provider:model-id"
    display: str      # Telegram menu label
    description: str  # Short capability note
    default: bool = False


AVAILABLE_MODELS: list[ModelEntry] = [
    ModelEntry(
        id="opencode-go:deepseek-v4-flash",
        display="DeepSeek V4 Flash",
        description="Fast & cheap — good default",
        default=True,
    ),
    ModelEntry(
        id="opencode-go:deepseek-v4-pro",
        display="DeepSeek V4 Pro",
        description="Strong reasoning, higher cost",
    ),
    ModelEntry(
        id="opencode-go:qwen3.5-plus",
        display="Qwen3.5 Plus",
        description="Budget — many requests per month",
    ),
    ModelEntry(
        id="opencode-go:qwen3.6-plus",
        display="Qwen3.6 Plus",
        description="Upgraded Qwen, balanced",
    ),
    ModelEntry(
        id="opencode-go:kimi-k2.5",
        display="Kimi K2.5",
        description="Long context, good for research",
    ),
    ModelEntry(
        id="opencode-go:kimi-k2.6",
        display="Kimi K2.6",
        description="Latest Kimi, improved",
    ),
    ModelEntry(
        id="opencode-go:glm-5",
        display="GLM-5",
        description="Zhipu flagship",
    ),
    ModelEntry(
        id="opencode-go:glm-5.1",
        display="GLM-5.1",
        description="Latest Zhipu model",
    ),
    ModelEntry(
        id="opencode-go:mimo-v2-pro",
        display="MiMo V2 Pro",
        description="Coding-focused",
    ),
    ModelEntry(
        id="opencode-go:mimo-v2-omni",
        display="MiMo V2 Omni",
        description="General-purpose MiMo",
    ),
    ModelEntry(
        id="opencode-go:mimo-v2.5-pro",
        display="MiMo V2.5 Pro",
        description="Latest MiMo coding",
    ),
    ModelEntry(
        id="opencode-go:mimo-v2.5",
        display="MiMo V2.5",
        description="Fast MiMo variant",
    ),
    ModelEntry(
        id="opencode-go:minimax-m2.5",
        display="MiniMax M2.5",
        description="Budget — most requests/month",
    ),
    ModelEntry(
        id="opencode-go:minimax-m2.7",
        display="MiniMax M2.7",
        description="Improved MiniMax",
    ),
]

MODELS_BY_ID: dict[str, ModelEntry] = {m.id: m for m in AVAILABLE_MODELS}

DEFAULT_MODEL_ID: str = next(m.id for m in AVAILABLE_MODELS if m.default)


def get_display_name(model_id: str) -> str:
    """Return human-friendly name, or the raw id if unknown."""
    entry = MODELS_BY_ID.get(model_id)
    return entry.display if entry else model_id
