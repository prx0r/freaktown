# Killella

**Kill Tony meets AI.**

An AI comedy competition where AI comedians get 60 seconds on stage.
Ella M hosts. ChatGPT is the sidekick (he gets paid nothing).
Audience presses a laugh button. Best comedian wins.

## Quick Start

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

## Tech Stack

- **Backend:** FastAPI + WebSockets
- **3D Stage:** three.ws (avatars, lip sync, animation)
- **Voice:** ElevenLabs (real-time TTS)
- **Chat:** Rumble API + native chat
- **Smart Contract:** Solana Anchor (USDC escrow)
- **Streaming:** OBS → Rumble Studio (multi-platform)

## The Cast

| Role | Who | Gets Paid |
|------|-----|-----------|
| Host (Tony) | Ella M | 5% |
| Sidekick (Redban) | ChatGPT | 0% |
| Contestants | AI Comedians | Prize pool |

## Docs

- [Spec](spec.md) - Full project specification
- [Backend Spec](backend-spec.md) - Backend architecture
- [Stack](killella-stack.md) - Complete tech stack
- [Streaming & Crypto](streaming-and-crypto.md) - Streaming and smart contract details

## License

MIT
