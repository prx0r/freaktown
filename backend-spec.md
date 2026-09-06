# KILLELLA Backend Spec

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| API | FastAPI | Async, WebSocket native, Python |
| Real-time | WebSockets | Bidirectional crowd interaction |
| Database | SQLite → PostgreSQL | Start simple, scale later |
| Voice | ElevenLabs | Real-time streaming TTS |
| 3D Stage | three.ws | Avatars, lip sync, animation |
| Chat | cocorum (Rumble API) | Python wrapper, auto-refresh |
| Smart Contract | Solana Anchor (Rust) | USDC escrow, staking |
| Streaming | OBS → Rumble Studio | Multi-platform output |
| Queue | Redis | Pub/sub for multi-server scaling |

## Architecture

```
                    ┌──────────────────┐
                    │   OBS STUDIO     │
                    │  (stream output)  │
                    └────────┬─────────┘
                             │ RTMP
                    ┌────────▼─────────┐
                    │  Rumble Studio   │
                    │ (multi-platform) │
                    └──────────────────┘

┌─────────────────────────────────────────────────────────┐
│                    KILLELLA BACKEND                      │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  FastAPI Server (main.py)                        │   │
│  │                                                   │   │
│  │  REST Endpoints:                                  │   │
│  │    POST /api/episode          create episode      │   │
│  │    GET  /api/episode/{id}     get episode state   │   │
│  │    POST /api/comedian         register comedian   │   │
│  │    POST /api/episode/{id}/enter  enter episode    │   │
│  │    GET  /api/scores/{id}      get episode scores  │   │
│  │    GET  /api/prize/{id}       get prize pool      │   │
│  │                                                   │   │
│  │  WebSocket Endpoints:                             │   │
│  │    WS /ws/crowd/{episode_id}  laugh/clap input   │   │
│  │    WS /ws/chat/{episode_id}   aggregated chat    │   │
│  │    WS /ws/stage/{episode_id}  stage events       │   │
│  │    WS /ws/scores/{episode_id} live score updates │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐        │
│  │ Show        │  │ Crowd      │  │ Judge      │        │
│  │ Controller  │  │ Scorer     │  │ Engine     │        │
│  │ (state      │  │ (laugh     │  │ (Ella +    │        │
│  │  machine)   │  │  agg)      │  │  ChatGPT)  │        │
│  └────────────┘  └────────────┘  └────────────┘        │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐        │
│  │ Chat       │  │ Voice      │  │ Prize      │        │
│  │ Aggregator │  │ Controller │  │ Manager    │        │
│  │ (Rumble +  │  │ (ElevenLabs│  │ (Solana    │        │
│  │  native)   │  │  streaming)│  │  escrow)   │        │
│  └────────────┘  └────────────┘  └────────────┘        │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Show Controller (State Machine)

```python
# Episode states
class EpisodeState(Enum):
    REGISTRATION = "registration"    # Comedians signing up
    LOCKED = "locked"                # Entries closed, material submitted
    LIVE = "live"                    # Show is running
    JUDGING = "judging"              # Scores being calculated
    COMPLETED = "completed"          # Winner declared, prizes paid

# State transitions
REGISTRATION → LOCKED (deadline or max entries)
LOCKED → LIVE (stream goes live)
LIVE → JUDGING (last comedian finishes)
JUDGING → COMPLETED (winner declared)
```

### 2. Crowd Scorer

```python
class CrowdScorer:
    """Aggregates laugh/clap events in real-time"""
    
    async def on_event(self, episode_id: str, event: CrowdEvent):
        # event.type: "laugh" | "clap" | "boo" | "heckle"
        # event.intensity: 1-5
        # event.timestamp: float
        
        # Store in Redis for real-time aggregation
        await redis.lpush(f"crowd:{episode_id}", json.dumps(event))
        
        # Calculate running score
        score = await self.calculate_score(episode_id)
        
        # Broadcast to all connected clients
        await broadcast(f"scores:{episode_id}", {"crowd": score})
    
    async def calculate_score(self, episode_id: str) -> float:
        events = await redis.lrange(f"crowd:{episode_id}", 0, -1)
        laughs = [e for e in events if e["type"] == "laugh"]
        
        if not laughs:
            return 0.0
        
        # Laughs per minute
        duration = laughs[-1]["timestamp"] - laughs[0]["timestamp"]
        lpm = len(laughs) / max(duration / 60, 0.1)
        
        # Average intensity
        avg_intensity = sum(e["intensity"] for e in laughs) / len(laughs)
        
        # Cluster bonus (3+ laughs within 3 seconds)
        clusters = self._find_clusters(laughs)
        cluster_bonus = len(clusters) * 5
        
        # Silence penalty (gaps > 5 seconds)
        silence_penalty = self._count_gaps(laughs) * 3
        
        raw = (lpm * 2) + (avg_intensity * 10) + cluster_bonus - silence_penalty
        return max(0, min(100, raw))
```

### 3. Judge Engine

```python
class JudgeEngine:
    """Ella M and ChatGPT scoring + commentary"""
    
    async def score_set(self, episode_id: str, comedian_id: str) -> dict:
        # Generate Ella's score and commentary
        ella_score = await self.generate_ella_score(comedian_id)
        
        # Generate ChatGPT's score (always too high)
        chat_score = await self.generate_chat_score(comedian_id)
        
        # Generate roast dialogue
        roast = await self.generate_roast(comedian_id, ella_score, chat_score)
        
        return {
            "ella_score": ella_score,
            "chat_score": chat_score,
            "roast": roast,
            "ella_voice": await self.voice.synthesize(roast["ella"], "ella_m"),
            "chat_voice": await self.voice.synthesize(roast["chat"], "chatgpt"),
        }
    
    async def generate_ella_score(self, comedian_id: str) -> dict:
        prompt = f"""You are Ella M, the host of Killella. 
        Score this comedian's set on a scale of 1-10.
        
        Comedian persona: {comedian.persona}
        Material: {comedian.material}
        Crowd score: {comedian.crowd_score}
        
        Be harsh but fair. Use your clinical dissection style.
        Return JSON: {{"score": float, "commentary": "string", "dimension_scores": {{...}}}}"""
        
        return await self.llm.generate(prompt, model="claude")
```

### 4. Chat Aggregator

```python
class ChatAggregator:
    """Combines Rumble chat + native killella.fun chat"""
    
    async def start(self, episode_id: str):
        # Start Rumble chat listener
        rumble_task = asyncio.create_task(
            self.listen_rumble(episode_id)
        )
        
        # Start native chat listener
        native_task = asyncio.create_task(
            self.listen_native(episode_id)
        )
        
        await asyncio.gather(rumble_task, native_task)
    
    async def listen_rumble(self, episode_id: str):
        api = RumbleAPI(RUMBLE_API_URL, refresh_rate=2)
        livestream = api.latest_livestream
        
        while livestream and livestream.is_live:
            for msg in livestream.chat.new_messages:
                await self.broadcast(episode_id, {
                    "platform": "rumble",
                    "user": msg.username,
                    "text": msg.text,
                    "timestamp": msg.created_on,
                })
            await asyncio.sleep(0.5)
    
    async def broadcast(self, episode_id: str, message: dict):
        await ws_manager.broadcast(f"chat:{episode_id}", message)
```

### 5. Voice Controller

```python
class VoiceController:
    """Real-time TTS via ElevenLabs streaming"""
    
    def __init__(self):
        self.client = ElevenLabs(api_key=ELEVENLABS_KEY)
        self.voices = {
            "ella_m": "EllaMVoiceID",
            "chatgpt": "ChatGPTVoiceID",
            # Comedians added dynamically
        }
    
    async def synthesize_streaming(self, text: str, voice: str) -> AudioStream:
        """Stream audio for real-time playback"""
        audio_stream = self.client.text_to_speech.convertAsStream(
            text=text,
            voice_id=self.voices[voice],
            model_id="eleven_turbo_v2",
            output_format="pcm_16000",
        )
        return audio_stream
    
    async def play_to_obs(self, audio_stream: AudioStream):
        """Route audio to OBS via virtual cable"""
        # Pipe to virtual audio device
        # OBS picks up the audio automatically
        pass
```

### 6. Prize Manager

```python
class PrizeManager:
    """Solana smart contract interaction"""
    
    def __init__(self):
        self.rpc_url = "https://api.mainnet-beta.solana.com"
        self.program_id = KILLELLA_PROGRAM_ID
    
    async def enter_episode(self, episode_id: str, comedian_wallet: str, amount: float) -> str:
        """Comedian deposits USDC into escrow"""
        # Build transaction
        tx = await self.build_enter_tx(episode_id, comedian_wallet, amount)
        # Send and confirm
        signature = await self.send_transaction(tx)
        return signature
    
    async def confirm_appearance(self, episode_id: str, comedian_id: str) -> str:
        """Called by oracle after comedian performs"""
        tx = await self.build_confirm_tx(episode_id, comedian_id)
        signature = await self.send_transaction(tx)
        return signature
    
    async def declare_winner(self, episode_id: str, winner_id: str) -> str:
        """Ella M declares the winner"""
        tx = await self.build_winner_tx(episode_id, winner_id)
        signature = await self.send_transaction(tx)
        return signature
    
    async def claim_prize(self, episode_id: str) -> str:
        """Winner withdraws their prize"""
        tx = await self.build_claim_tx(episode_id)
        signature = await self.send_transaction(tx)
        return signature
```

### 7. WebSocket Manager

```python
class ConnectionManager:
    """Manages all WebSocket connections"""
    
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        if channel not in self.connections:
            self.connections[channel] = []
        self.connections[channel].append(websocket)
    
    async def disconnect(self, websocket: WebSocket, channel: str):
        self.connections[channel].remove(websocket)
    
    async def broadcast(self, channel: str, data: dict):
        if channel in self.connections:
            dead = []
            for conn in self.connections[channel]:
                try:
                    await conn.send_json(data)
                except:
                    dead.append(conn)
            for conn in dead:
                self.connections[channel].remove(conn)
```

## Database Schema (SQLite → PostgreSQL)

```sql
-- Episodes
CREATE TABLE episodes (
    id TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'registration',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    winner_id TEXT,
    prize_pool REAL DEFAULT 0,
    entry_fee REAL DEFAULT 5.0,
    max_comedians INTEGER DEFAULT 10
);

-- Comedians
CREATE TABLE comedians (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    persona TEXT,
    avatar_id TEXT,
    voice_id TEXT,
    wallet_address TEXT,
    wins INTEGER DEFAULT 0,
    earnings REAL DEFAULT 0,
    reputation INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Episode Entries
CREATE TABLE episode_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT REFERENCES episodes(id),
    comedian_id TEXT REFERENCES comedians(id),
    escrow_tx TEXT,
    appearance_confirmed BOOLEAN DEFAULT FALSE,
    material_hash TEXT,
    entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(episode_id, comedian_id)
);

-- Scores
CREATE TABLE scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT REFERENCES episodes(id),
    comedian_id TEXT REFERENCES comedians(id),
    crowd_score REAL,
    ella_score REAL,
    chat_score REAL,
    survival_score REAL,
    final_score REAL,
    ella_commentary TEXT,
    chat_commentary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crowd Events (for analytics, not real-time)
CREATE TABLE crowd_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id TEXT REFERENCES episodes(id),
    comedian_id TEXT,
    event_type TEXT, -- laugh, clap, boo, heckle
    intensity INTEGER,
    timestamp REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## API Endpoints

### Episodes
```
POST   /api/episode                    Create new episode
GET    /api/episode/{id}               Get episode state
POST   /api/episode/{id}/start         Start the show (LOCKED → LIVE)
POST   /api/episode/{id}/next          Advance to next comedian
POST   /api/episode/{id}/end           End the show
GET    /api/episode/{id}/scores        Get all scores
GET    /api/episode/{id}/leaderboard   Get season leaderboard
```

### Comedians
```
POST   /api/comedian                   Register comedian
GET    /api/comedian/{id}              Get comedian profile
PUT    /api/comedian/{id}              Update comedian
GET    /api/comedian/{id}/history      Get performance history
```

### Entries
```
POST   /api/episode/{id}/enter         Enter episode (deposit USDC)
POST   /api/episode/{id}/confirm/{comedian_id}  Confirm appearance
GET    /api/episode/{id}/entries       List all entries
```

### Scoring
```
POST   /api/episode/{id}/score/{comedian_id}    Trigger scoring
GET    /api/episode/{id}/scores                  Get all scores
POST   /api/episode/{id}/winner                  Declare winner
```

### WebSocket
```
WS     /ws/crowd/{episode_id}          Crowd interaction (laugh/clap)
WS     /ws/chat/{episode_id}           Aggregated chat feed
WS     /ws/stage/{episode_id}          Stage events (comedian enters, timer)
WS     /ws/scores/{episode_id}         Live score updates
```

## Project Structure

```
killella/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Settings, env vars
│   ├── models/
│   │   ├── __init__.py
│   │   ├── episode.py             # Episode model
│   │   ├── comedian.py            # Comedian model
│   │   ├── score.py               # Score model
│   │   └── crowd.py               # Crowd event model
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── episodes.py            # Episode CRUD
│   │   ├── comedians.py           # Comedian CRUD
│   │   ├── entries.py             # Entry management
│   │   └── scoring.py             # Score endpoints
│   ├── ws/
│   │   ├── __init__.py
│   │   ├── manager.py             # WebSocket connection manager
│   │   ├── crowd.py               # Crowd WebSocket handler
│   │   ├── chat.py                # Chat WebSocket handler
│   │   └── stage.py               # Stage WebSocket handler
│   ├── services/
│   │   ├── __init__.py
│   │   ├── show_controller.py     # Episode state machine
│   │   ├── crowd_scorer.py        # Laugh aggregation
│   │   ├── judge_engine.py        # Ella + ChatGPT scoring
│   │   ├── chat_aggregator.py     # Multi-platform chat
│   │   ├── voice_controller.py    # ElevenLabs TTS
│   │   └── prize_manager.py       # Solana contract calls
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py            # DB connection
│   │   └── migrations.py          # Schema setup
│   └── utils/
│       ├── __init__.py
│       └── crypto.py              # Wallet helpers
├── contracts/
│   ├── programs/
│   │   └── killella/
│   │       ├── src/
│   │       │   ├── lib.rs         # Main program
│   │       │   ├── state.rs       # Account structs
│   │       │   ├── errors.rs      # Custom errors
│   │       │   └── instructions/  # Instruction handlers
│   │       │       ├── mod.rs
│   │       │       ├── enter.rs
│   │       │       ├── confirm.rs
│   │       │       ├── declare.rs
│   │       │       └── claim.rs
│   │       └── Cargo.toml
│   ├── Anchor.toml
│   └── tests/
│       └── killella.ts
├── frontend/
│   ├── index.html                 # Main page
│   ├── laugh-button.js            # WebSocket laugh client
│   ├── chat-feed.js               # Aggregated chat
│   ├── score-overlay.html         # OBS overlay
│   └── assets/
│       └── style.css
├── stage/
│   ├── ella-m-config.json         # three.ws agent config
│   ├── chatgpt-config.json        # three.ws agent config
│   └── stage-scene.json           # three.ws scene
├── requirements.txt
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Environment Variables

```bash
# Backend
DATABASE_URL=sqlite:///killella.db
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key

# ElevenLabs
ELEVENLABS_API_KEY=your-key
ELEVENLABS_ELLA_VOICE_ID=your-voice-id
ELEVENLABS_CHAT_VOICE_ID=your-voice-id

# LLM
ANTHROPIC_API_KEY=your-key
OPENAI_API_KEY=your-key

# Rumble
RUMBLE_API_URL=your-rumble-api-url

# Solana
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
KILLELLA_PROGRAM_ID=your-program-id
USDC_MINT=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v

# three.ws
THREE_WS_API_KEY=your-key
```

## Deployment

### Docker Compose
```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - redis
      - postgres
  
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
  
  postgres:
    image: postgres:alpine
    environment:
      POSTGRES_DB: killella
      POSTGRES_USER: killella
      POSTGRES_PASSWORD: killella
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

### Quick Start
```bash
# Clone
git clone https://github.com/YOUR_USER/killella.git
cd killella

# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Smart Contract
cd contracts
anchor build
anchor deploy

# Frontend (for OBS overlay)
cd frontend
python3 -m http.server 8080
```
