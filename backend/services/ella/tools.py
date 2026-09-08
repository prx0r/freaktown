"""Ella tools — how the realtime model operates the theatre.

Each tool maps to a canonical EpisodeRoom command. Tools marked
implemented execute on the stage today; tools marked planned reserve
their contract (event type + payload shape) for the lighting/replay
renderer work. Nothing here invents authority Ella doesn't have:
award_ticket and end_set emit events the existing pipeline honors.
"""

from dataclasses import dataclass, field


@dataclass
class EllaTool:
    name: str
    description: str
    command: str  # EpisodeRoom command type
    implemented: bool
    parameters: dict = field(default_factory=dict)

    def to_command(self, args: dict) -> dict:
        """Build the command payload for POST /live/:ep/command."""
        payload = {"actor": "ella", **args}
        return {"type": self.command, "payload": payload}


ELLA_TOOLS: dict[str, EllaTool] = {
    "cut_camera": EllaTool(
        name="cut_camera",
        description="Cut the program camera to a preset.",
        command="camera.cut",
        implemented=True,
        parameters={"camera": "WIDE_STAGE|COMIC_MEDIUM|COMIC_CLOSE|SIDE_STAGE|PANEL_WIDE|ELLA_CLOSE|CHATGPT_CLOSE|STREAM_CLOSE",
                      "set_time_ms": 0},
    ),
    "play_sting": EllaTool(
        name="play_sting",
        description="Play a sting/SFX over the program mix.",
        command="audio.sfx.play",
        implemented=True,
        parameters={"name": "rimshot|bomb|success|boo|laugh|drum_hit|..."},
    ),
    "speak": EllaTool(
        name="speak",
        description="Say a line as Ella (live dialogue, not verdict).",
        command="stage.speak",
        implemented=True,
        parameters={"text": "line to speak"},
    ),
    "award_ticket": EllaTool(
        name="award_ticket",
        description="Issue a Golden Ticket to the active performer.",
        command="award.golden_ticket",
        implemented=True,
        parameters={"appearance_id": "..."},
    ),
    "end_set": EllaTool(
        name="end_set",
        description="End the current set (mercy rule).",
        command="performance.end",
        implemented=True,
        parameters={"performance_id": "..."},
    ),
    "next_character": EllaTool(
        name="next_character",
        description="Bring the next performer on stage.",
        command="character.enter",
        implemented=True,
        parameters={"appearanceId": "..."},
    ),
    # ── Planned (contract reserved, no stage executor yet) ──────────
    "dim_lights": EllaTool(
        name="dim_lights",
        description="Dim the house lights (lighting renderer).",
        command="lights.dim", implemented=False,
        parameters={"level": "0.0-1.0"},
    ),
    "spotlight": EllaTool(
        name="spotlight",
        description="Spotlight a performer or judge (lighting renderer).",
        command="lights.spot", implemented=False,
        parameters={"target": "performer|ella|chatgpt|stream"},
    ),
    "look_at": EllaTool(
        name="look_at",
        description="Ella's gaze target (avatar renderer).",
        command="ella.look", implemented=False,
        parameters={"target": "performer|chatgpt|audience"},
    ),
    "show_comment": EllaTool(
        name="show_comment",
        description="Flash an audience comment on screen (overlay renderer).",
        command="stage.comment", implemented=False,
        parameters={"text": "..."},
    ),
    "show_replay": EllaTool(
        name="show_replay",
        description="Replay a moment (replay renderer).",
        command="stage.replay", implemented=False,
        parameters={"from_seq": 0, "to_seq": 0},
    ),
    "interrupt_chatgpt": EllaTool(
        name="interrupt_chatgpt",
        description="Cut ChatGPT's mic (dialogue director).",
        command="dialogue.interrupt", implemented=False,
        parameters={"target": "chatgpt"},
    ),
}


def get_tool(name: str) -> EllaTool:
    tool = ELLA_TOOLS.get(name)
    if not tool:
        raise ValueError(f"unknown Ella tool: {name}")
    return tool


def implemented_tools() -> list[str]:
    return sorted(name for name, tool in ELLA_TOOLS.items() if tool.implemented)


def planned_tools() -> list[str]:
    return sorted(name for name, tool in ELLA_TOOLS.items() if not tool.implemented)
