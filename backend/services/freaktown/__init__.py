"""Black Room adapter — freaktown artifacts in, killella performances out.

Read-only with respect to the freaktown repo: schema authority stays
freaktown.delivery.v1, we just accept the full schema here.
"""

from backend.services.freaktown.bundle import (
    SCHEMA_VERSION,
    PERFORMANCE_SCHEMA_VERSION,
    BEAT_TYPES,
    SPECIES_MAP,
    BundleValidation,
    BeatSpan,
    species_to_body,
    bundle_slug,
    validate_delivery,
    validate_bundle,
    bundle_to_score,
    spans_from_offsets,
    estimate_spans,
    words_from_beats,
    build_performance_manifest,
)

__all__ = [
    "SCHEMA_VERSION",
    "PERFORMANCE_SCHEMA_VERSION",
    "BEAT_TYPES",
    "SPECIES_MAP",
    "BundleValidation",
    "BeatSpan",
    "species_to_body",
    "bundle_slug",
    "validate_delivery",
    "validate_bundle",
    "bundle_to_score",
    "spans_from_offsets",
    "estimate_spans",
    "words_from_beats",
    "build_performance_manifest",
]
