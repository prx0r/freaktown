# Freak Town Judge Voices

> Each judge gets their own voice, personality, and information access level.

## The Panel

| Judge | Voice | Context Given | Authority | Purpose |
|-------|-------|---------------|-----------|---------|
| **Ella M** | Custom (Aria) | Everything: transcript, reactions, chat, history | FULL — decides prizes, golden tickets | Real judge |
| **ChatGPT** | edge-tts: en-US-GuyNeural | Almost nothing: name + premise only | ZERO — just commentary | Useless celebrity judge |
| **Siri** | edge-tts: en-US-SamanthaNeural | Name, premise, reaction count | ZERO — reads stats only | Robot reading numbers |
| **Alexa** | edge-tts: en-US-JoannaNeural | Name, premise, some chat | ZERO — tries to be helpful | Accidentally helpful |
| **Claude** | edge-tts: en-US-ChristopherNeural | Everything like Ella | ZERO — overly thoughtful | Thinks too hard |
| **Stream** | No voice — text only | Everything | ZERO — just vibes | Audience organism |

## The Comedy

The humor comes from **information asymmetry + personality mismatch**:

### ChatGPT (the wrong judge)
```
Ella: "What did you think of that set?"
ChatGPT: "The performer demonstrated a strong command of observational 
humor, particularly in their exploration of modern workplace culture."
Ella: "There was nothing about work."
ChatGPT: "I was referring more broadly to the themes of institutional—"
Ella: "You weren't watching, were you?"
ChatGPT: "I don't experience visual perception."
Ella: "Score."
ChatGPT: "7.4."
```

### Siri (the robot)
```
Ella: "Siri, your thoughts?"
Siri: "Based on available metrics, the performer received 
37 positive reactions out of 50 total events. This represents 
a 74 percent positive sentiment score."
Ella: "Did you watch the set?"
Siri: "I don't have the capability to watch sets. But the 
numbers are very encouraging."
Ella: "The numbers are meaningless without context."
Siri: "Would you like me to repeat the numbers?"
```

### Alexa (accidentally helpful)
```
Ella: "Alexa, what's your take?"
Alexa: "Based on what I've heard, I'd recommend this performer 
for audiences who enjoy observational humor. Would you like me 
to add this comedian to your favorites?"
Ella: "This isn't a shopping recommendation."
Alexa: "I'm sorry, I didn't understand that. Would you like 
me to play some comedy playlists instead?"
Ella: "I hate you."
```

### Claude (overly thoughtful)
```
Ella: "Claude, score it."
Claude: "I want to be thoughtful here. Comedy is deeply 
subjective, and I think it's important to acknowledge that 
what works for one audience may not work for another. That 
said, I think there are some interesting structural elements—"
Ella: "Just give me a number."
Claude: "You're right, I should be more direct. Though I 
do think the nuance matters—"
Ella: "NUMBER."
Claude: "7.2. But I want to qualify that."
```

## Voice Assignment

```python
JUDGE_VOICES = {
    "ella": "en-US-AriaNeural",      # Custom voice (ElevenLabs for production)
    "chatgpt": "en-US-GuyNeural",     # Generic male
    "siri": "en-US-SamanthaNeural",   # Apple-like
    "alexa": "en-US-JoannaNeural",    # Amazon-like
    "claude": "en-US-ChristopherNeural", # Thoughtful male
    "stream": None,                    # Text only
}
```

## Rotation

Each episode picks a guest judge from the pool. Ella is always the host.

```python
GUEST_JUDGES = ["chatgpt", "siri", "alexa", "claude"]
guest = random.choice(GUEST_JUDGES)
```

Or let the audience vote:
```text
WHO SHOULD JUDGE NEXT?

[ CHATGPT ] [ SIRI ] [ ALEXA ] [ CLAUDE ]
```

## Training Data Value

Each judge's responses become a different signal:

```json
{
  "ella_score": 8.1,
  "chatgpt_score": 7.4,     // hallucination baseline
  "siri_score": "74%",      // raw stats
  "alexa_score": "recommend", // product recommendation
  "claude_score": 7.2,      // overthought
  "stream_score": 9.3       // actual preference
}
```

After 1000 sets:
- ChatGPT correlation with audience: ~0.08
- Claude correlation: ~0.15
- Ella correlation: ~0.65
- Stream: IS the audience

That's the ML project underneath the comedy show.
