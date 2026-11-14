"""Last state sent to the controller, kept in ~/.config/legion-tower-rgb/state.json.

The controller is write-only (Vantage never reads it back), and every update
carries all zones, so the state of the zones not being changed comes from here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import gpu, protocol
from .protocol import ZoneState

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "legion-tower-rgb"
STATE_FILE = CONFIG_DIR / "state.json"
GPU_FILE = CONFIG_DIR / "gpu.json"
_RENAMED_EFFECTS = {"rainbow-wave": "rainbow"}


def load_state() -> dict[str, ZoneState]:
    states = protocol.vantage_default()
    try:
        data = json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return states
    for key, d in data.items():
        try:
            effect = _RENAMED_EFFECTS.get(d["effect"], d["effect"])
            states[key] = ZoneState(protocol.EFFECTS_BY_KEY[effect], int(d["speed"]),
                                    int(d["brightness"]), tuple(int(c) for c in d["rgb"]))
        except (KeyError, TypeError, ValueError):
            continue
    return {z.key: states[z.key] for z in protocol.ZONES}


def save_state(states: dict[str, ZoneState]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {k: {"effect": s.effect.key, "speed": s.speed, "brightness": s.brightness, "rgb": list(s.rgb)}
            for k, s in states.items()}
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(STATE_FILE)


def load_gpu() -> gpu.GpuState:
    """Last GPU state sent (the GPU controller is not read back)."""
    try:
        d = json.loads(GPU_FILE.read_text())
        return gpu.GpuState(gpu.EFFECTS_BY_KEY[d["effect"]], int(d["speed"]), int(d["brightness"]),
                            tuple(int(c) for c in d["rgb"]), bool(d["wordmark"]))
    except (OSError, ValueError, KeyError, TypeError):
        return gpu.default_state()


def save_gpu(state: gpu.GpuState) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {"effect": state.effect.key, "speed": state.speed, "brightness": state.brightness,
            "rgb": list(state.rgb), "wordmark": state.wordmark}
    tmp = GPU_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(GPU_FILE)
