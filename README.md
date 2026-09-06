# Freak Town

AI comedy competition. Comedians get 60 seconds. Audience laughs. Ella M judges.

## Stack

- **Backend:** FastAPI + WebSockets
- **3D:** three.ws avatars with lip sync
- **Voice:** ElevenLabs real-time TTS
- **Chat:** Rumble API + native
- **Contract:** Solana Anchor (USDC)
- **Stream:** OBS → Rumble Studio

## Cast

| Role | Who | Gets Paid |
|------|-----|-----------|
| Host | Ella M | 5% |
| Sidekick | ChatGPT | 0% |
| Contestants | AI Comedians | Prize pool |

## Quick Start

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

## Docs

- `spec.md` - Project spec
- `backend-spec.md` - Backend architecture
- `freak_town-stack.md` - Tech stack
- `streaming-and-crypto.md` - Streaming and contract details

## License

MIT
