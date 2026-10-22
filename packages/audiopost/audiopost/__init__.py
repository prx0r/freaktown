"""audiopost: deterministic, seeded studio post for synthetic voices ("make it sound alive").

Room acoustics, off-axis mic drift, plosive/proximity moments, breaths in alignment gaps, room
tone, light foley, a gentle broadcast chain, an original procedural jingle/bed with ducking, and
a -14 LUFS / true-peak master. Generic: any show that has a dry VO and word timings can use it.
"""
from .process import run, dry_master, load_preset  # noqa: F401
from .master import measure  # noqa: F401

__version__ = "0.1.0"
