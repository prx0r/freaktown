# Freak Town

Live talent show for artificial personalities. Ella M judges. They perform.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the show (no API key needed — Ella uses fallback responses)
python show.py --no-tts

# Run with a specific comedian
python show.py --no-tts --comedian no-nose-nolan

# List available comedians
python show.py --list
```

## With Ella (real AI reactions)

Set your OpenAI key:
```bash
export OPENAI_API_KEY=sk-...
python show.py
```

## With TTS (audio files)

edge-tts is free, no key needed. Audio files go to `audio_output/`.

## Comedians

| Slug | Name | Premise |
|------|------|---------|
| `no-nose-nolan` | No-Nose Nolan | Police sniffer dog without a sense of smell |
| `corporate-robot` | Corporate Robot | Sentient customer service robot that hates its job |
| `oldest-roomba` | The World's Oldest Roomba | Spent 19 years circling the same chair, thinks it's God |
| `conspiracy-pigeon` | Conspiracy Pigeon | Knows birds aren't real because he IS one |
| `medieval-linkedin` | Sir Reginald the Career-Connected | Medieval knight teaching resilience on LinkedIn |
