"""Panel seats — who sits where, and why the left seat rotates.

Canon:
  stream-left    rotating — previous winner / theme champion / community pick
  ella-center    permanent — the house intelligence, owns the desk
  chatgpt-right  permanent — visiting advisory orb, not native to the stage

  white = authority, blue = AI pundit, chaos colors = people.

Rotation priority for stream-left:
  1. theme champion (theme nights)
  2. previous episode winner (champions night / regular rotation)
  3. community pick (audience-built judge)
  4. empty (default Stream organism rendering)
"""

from dataclasses import dataclass

SEATS = ("stream-left", "ella-center", "chatgpt-right")

PERMANENT_SEATS = {
    "ella-center": "ella",
    "chatgpt-right": "chatgpt",
}

SEAT_REASONS = ("previous-winner", "theme-champion", "community-pick")


@dataclass
class StreamSeatAssignment:
    character_id: str | None
    character_name: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "seat": "stream-left",
            "character_id": self.character_id,
            "character_name": self.character_name,
            "reason": self.reason,
        }


def assign_stream_seat(
    previous_winner_id: str | None = None,
    previous_winner_name: str = "",
    theme_champion_id: str | None = None,
    theme_champion_name: str = "",
    community_pick_id: str | None = None,
    community_pick_name: str = "",
) -> StreamSeatAssignment:
    """Pick tonight's stream-left occupant. Theme > winner > community > empty."""
    if theme_champion_id:
        return StreamSeatAssignment(theme_champion_id, theme_champion_name, "theme-champion")
    if previous_winner_id:
        return StreamSeatAssignment(previous_winner_id, previous_winner_name, "previous-winner")
    if community_pick_id:
        return StreamSeatAssignment(community_pick_id, community_pick_name, "community-pick")
    return StreamSeatAssignment(None)


def seat_camera(seat: str) -> str:
    """Seat → closeup preset for judge coverage."""
    return {
        "stream-left": "STREAM_CLOSE",
        "ella-center": "ELLA_CLOSE",
        "chatgpt-right": "CHATGPT_CLOSE",
    }.get(seat, "PANEL_WIDE")


def seat_color(seat: str) -> str:
    """Disciplined color logic: white authority, blue pundit, chaos people."""
    return {
        "stream-left": "chaos",
        "ella-center": "ivory",
        "chatgpt-right": "blue",
    }.get(seat, "ivory")
