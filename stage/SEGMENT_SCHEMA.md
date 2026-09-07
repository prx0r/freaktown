# Optional TTS-aware segment schema

The UI is backward-compatible with the current `/api/set` response (`title`, `text`, `audio`, `show_number`). If the backend later emits segment timing/emotion metadata, the front end automatically uses it.

```json
{
  "title": "The Hosting Gig",
  "audio": "/audio/ella_123.mp3",
  "show_number": 12,
  "text": "Full fallback transcript...",
  "segments": [
    {
      "text": "People think hosting a comedy show is easy.",
      "start_ms": 0,
      "end_ms": 2280,
      "emotion": "deadpan",
      "intensity": 0.62,
      "pace": 0.91,
      "pause_after_ms": 540
    }
  ]
}
```

## Visual mapping

- `emotion` -> bubble hue.
- `pace` -> bubble width. Fast lines stretch wider; slow lines stay compact.
- `pause_after_ms` -> physical whitespace after the bubble.
- `intensity` -> saturation/glow.
- `start_ms/end_ms` -> exact reveal/highlight timing against audio playback.

Recommended emotion vocabulary: `neutral`, `deadpan`, `joy`, `playful`, `tension`, `surprise`, `warm`.

If the TTS provider exposes word/segment boundaries, normalize them into this schema server-side. If not, the bundled JS estimates line timings from audio duration, word count and punctuation so the existing server works without modification.
