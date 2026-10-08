"""Comedy compiler — corpus → rhythms → director → evaluator.

The architecture plan: teaching Freaktown how comedy behaves in TIME, not
what it says. Persona stays Freaktown-native; the corpus compiles into
timing grammars that feed delivery.v1.

    comedy/corpus.py      external text → anonymous structural/timing grammar
    comedy/rhythms.py     learned archetypes (DRY MISDIRECTION, MANIC, …)
    comedy/director.py    bit + character profile → freaktown.delivery.v1
    comedy/evaluator.py   predicted audience response (+ learn from events)

Invariant: Freaktown owns silence. TTS speaks chunks; these modules own the
millisecond pauses (cf. tts_provider.py: "Freak Town owns timing").
"""
from .corpus import analyze
from .director import compile_delivery
from .evaluator import predict, learn

__all__ = ["analyze", "compile_delivery", "predict", "learn"]
