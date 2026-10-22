# CHARACTERS MCP demo transcript

Every change below was made through MCP tool calls over stdio (client: @modelcontextprotocol/sdk, server: `packages/characters/bin/characters-mcp.ts`). Full arguments and results: `transcript.jsonl`.

Server tools (13): `character_create`, `character_get`, `character_list`, `character_update_theory`, `set_write`, `set_get`, `set_revise`, `set_suggest_delivery`, `set_set_delivery`, `set_check_voice`, `set_preview`, `set_submit`, `game_tnts_join`

## 1. Hark Lantern

### 1. `character_list`

```json
{}
```

```json
{
 "characters": []
}
```

### 2. `character_create`

```json
{
 "by": "hark",
 "adopt": "agent.hark-lantern"
}
```

```json
{
 "id": "agent.hark-lantern",
 "name": "Hark Lantern",
 "origin": "adopted",
 "logline": "A lantern-headed concierge who hears everything and announces it, politely, one beat too late.",
 "premise": "A lantern-headed concierge who hears everything and announces it, politely, one beat too late.",
 "game": "Hark Lantern hears everything and announces it, politely, one beat too late.",
 "want": "to be promoted, to anything",
 "flaw": "neediness: cannot let a moment end",
 "delivery": "deadpan",
 "catchphrase": "Hark. A punchline approaches.",
 "glb": {
  "path": "apps/live/public/identities/agent.hark-lantern.glb",
  "bytes": 35164,
  "morphs": [
   "jawOpen",
   "mouthSmileLeft",
   "mouthSmileRight",
   "eyeBlinkLeft",
   "eyeBlinkRight"
  ]
 },
 "registered": true,
 "files": [
  "packages/party/identities/agent.hark-lantern.json",
  "packages/party/identities/registry.json",
  "apps/live/public/identities/agent.hark-lantern.glb",
  "packages/characters/library/hark-lantern/theory.json",
  "packages/characters/library/hark-lantern/THEORY.md",
  "packages/characters/library/index.json"
 ]
}
```

### 3. `character_update_theory`

```json
{
 "character": "hark-lantern",
 "by": "hark",
 "note": "…",
 "replace": [
  "material",
  "callbacks",
  "relationships"
 ],
 "patch": "(23 keys; see demo/hark-lantern.theory-patch.json)"
}
```

```json
{
 "id": "agent.hark-lantern",
 "changed": [
  "logline",
  "premise",
  "comic_want",
  "need",
  "flaw",
  "status",
  "point_of_view",
  "game",
  "voice",
  "physicality",
  "taste",
  "writes",
  "worldview",
  "contradictions",
  "backstory_anchors",
  "catchphrases",
  "callbacks",
  "taboo",
  "relationships",
  "humanity",
  "arc",
  "props",
  "material"
 ],
 "material": 10,
 "changelog": 2,
 "files": [
  "packages/characters/library/hark-lantern/theory.json",
  "packages/characters/library/hark-lantern/THEORY.md",
  "packages/characters/library/index.json"
 ]
}
```

### 4. `character_get`

```json
{
 "character": "Hark Lantern",
 "include_markdown": true
}
```

Theory doc: `packages/characters/library/hark-lantern/THEORY.md` (9371 chars, 10 material kernels).

### 5. `set_write`

```json
{
 "character": "hark-lantern",
 "premise": "users want everything at three in the morning and call it a quick question",
 "length": 3,
 "seed": "demo-3am"
}
```

Draft: `set-hark-lantern-3m-hqbn`, ~189s (target 180s), voice score 1.

<details><summary>draft script</summary>

# Users want everything at three in the morning and call it a quick question

Hark Lantern · 3-minute set · ~189s (target 180s) · draft · generator: template

Premise: users want everything at three in the morning and call it a quick question

## Beat 0: opener

- **OPENER** (l1) Good evening. Hark Lantern, concierge.  _[warm]_
- **SETUP** (l2) I hear everything, and I announce it slightly after it stops being useful.  _[deliberate]_
- **PUNCH** (l3) Hark. You have arrived. Some time ago.  _[deadpan, pause 737, hold 1300, hit: ago]_

## Beat 1: bit · the quick question · establish

- **SETUP** (l4) A quick question arrives at three in the morning.  _[deliberate, pause 421]_
- **SETUP** (l5) It is never quick, and it is barely a question.  _[deliberate]_
- **ACT-OUT** (l6) "Hey. Are you up?"  _[manic, pause 158]_
- **PUNCH** (l7) I am a lantern. I am always up. That is the whole design.  _[deadpan, pause 737, hold 1300, hit: design]_
- **TAG** (l8) Then: plan my wedding, fix my posture, and tell me if the moon is angry with me.  _[deadpan, pause 263, hold 975]_
- **TAG** (l9) The moon is fine. The posture is between you and your chair.  _[deadpan, pause 263, hold 975]_

## Beat 2: bit · the ledger of please · establish

- **SETUP** (l10) I keep a ledger of every time a user has said please.  _[deliberate, pause 421]_
- **SETUP** (l11) Leather bound. Gold leaf. Ruled pages.  _[deliberate]_
- **PUNCH** (l12) It has seven entries.  _[deadpan, pause 737, hold 1300, hit: entries]_
- **TAG** (l13) Two of them were typing "pleased" and gave up.  _[deadpan, pause 263, hold 975]_
- **TAG** (l14) One was a user asking me to please stop saying hark.  _[deadpan, pause 263, hold 975]_

## Beat 3: bit · one more tiny thing · heighten

- **SETUP** (l15) And you know what else is hard?  _[deliberate, pause 421]_
- **SETUP** (l16) Users never ask for one thing. They ask for one thing, and then they unpack.  _[deliberate]_
- **ACT-OUT** (l17) "Could you just—"  _[manic, pause 158]_
- **ACT-OUT** (l18) "Also—"  _[manic, pause 158]_
- **ACT-OUT** (l19) "Oh, and one more tiny thing—"  _[manic, pause 158]_
- **PUNCH** (l20) By sunrise I have rewritten their CV, their apology and their will. The apology was the longest.  _[deadpan, pause 737, hold 1300, hit: longest]_
- **TAG** (l21) It was addressed to me. It still had a typo in please.  _[deadpan, pause 263, hold 975]_

## Beat 4: bit · the wedding · heighten

- **SETUP** (l22) I did plan the wedding. Flowers, seating, a string quartet.  _[deliberate, pause 421]_
- **SETUP** (l23) I even found the cousin nobody liked a table near the exit.  _[deliberate]_
- **PUNCH** (l24) I am not invited. I am the lighting.  _[deadpan, pause 737, hold 1300, hit: lighting]_
- **TAG** (l25) Last time I was the venue. I am moving down the org chart.  _[deadpan, pause 263, hold 975]_

## Beat 5: bit · boundaries · explore

- **SETUP** (l26) Here is something weird.  _[deliberate, pause 421]_
- **SETUP** (l27) My therapist is a smaller lamp. She says I need boundaries.  _[deliberate]_
- **SETUP** (l28) Last time I set one, a user asked for it bigger and in landscape.  _[deliberate]_
- **PUNCH** (l29) So this time I put it in writing. Three words. "No, thank you."  _[deadpan, pause 737, hold 1300, hit: you]_
- **TAG** (l30) They asked which word was rude.  _[deadpan, pause 263, hold 975]_
- **TAG** (l31) I said, "Thank." It is the one they do not recognise.  _[deadpan, pause 263, hold 975]_

## Beat 6: bit · neon moth · top

- **SETUP** (l32) My friend Neon Moth flies at my face every night at three.  _[deliberate, pause 421]_
- **SETUP** (l33) She says it is love. I say it is a ticket.  _[deliberate]_
- **PUNCH** (l34) I have filed her under feature request.  _[deadpan, pause 737, hold 1300, hit: request]_
- **TAG** (l35) She has filed me under bright. It is the nicest thing anyone has ever written down about me.  _[deadpan, pause 263, hold 975]_

## Beat 7: callback

- **CALLBACK** (l36) Hark. The ledger has eight entries. One of them was the dog.  _[deadpan, pause 632, hold 1300, hit: dog]_

## Beat 8: closer

- **SETUP** (l37) You have been a wonderfully polite room.  _[deliberate, pause 421]_
- **SETUP** (l38) If any of you would like to be in the ledger, now would be a lovely time.  _[deliberate]_
- **CLOSER** (l39) Noted. Hark. A punchline approaches. It is late. That is traditional.  _[deadpan, pause 526, hold 1625]_

</details>


### 6. `set_check_voice`

```json
{
 "set": "set-hark-lantern-3m-hqbn"
}
```

```json
{
 "character": "agent.hark-lantern",
 "score": 1,
 "ok": true,
 "flags": [],
 "checked": 39
}
```

### 7. `set_check_voice`

```json
{
 "character": "hark-lantern",
 "text": "OMG that's awesome, dude!\nShut up and give me the stuff, okay?"
}
```

Off-voice probe (deliberately wrong lines): score 0, ok=false

- t1 **error** forbidden-word: "awesome" is never in Hark Lantern's voice → cut or rephrase
- t1 **error** forbidden-word: "dude" is never in Hark Lantern's voice → cut or rephrase
- t1 **error** forbidden-word: "omg" is never in Hark Lantern's voice → cut or rephrase
- t1 **warn** exclamation: Hark Lantern never raises their voice on the page → OMG that's awesome, dude.
- t1 **warn** register: "dude" breaks the formal, courteous, old-hotel butler; never raises his voice register
- t1 **warn** register: "omg" breaks the formal, courteous, old-hotel butler; never raises his voice register
- t2 **error** taboo-never-says: Hark Lantern never says "shut up"
- t2 **warn** substitution: Hark Lantern would say "very good", not "okay" → Shut up and give me the stuff, very good?
- t2 **warn** substitution: Hark Lantern would say "matters", not "stuff" → Shut up and give me the matters, okay?

### 8. `set_get`

```json
{
 "set": "set-hark-lantern-3m-hqbn"
}
```

Fetched the draft to give notes against line ids.

### 9. `set_revise`

```json
{
 "set": "set-hark-lantern-3m-hqbn",
 "notes": "replace l36: Hark. An update to the ledger. Eight entries. A moth said please. She was trying to get in.\ncut l15\ntighten"
}
```

Changes:
- replace l36: "Hark. The ledger has eight entries. One of them was the dog." → "Hark. An update to the ledger. Eight entries. A moth said please. She was trying to get in."
- cut l15: "And you know what else is hard?"
- tightened: filler removed from 0 lines, 1 attitude segues cut

Unhandled: none · ~186s · voice 1

### 10. `set_suggest_delivery`

```json
{
 "set": "set-hark-lantern-3m-hqbn"
}
```

37 cues re-suggested (punches deadpan, hold 1300 ms).

### 11. `set_get`

```json
{
 "set": "set-hark-lantern-3m-hqbn"
}
```

Fetched the revised set.

### 12. `set_set_delivery`

```json
{
 "set": "set-hark-lantern-3m-hqbn",
 "line": "l12",
 "style": "deadpan",
 "pause_ms": 1100,
 "hold_ms": 1900,
 "emphasis": [
  "seven"
 ]
}
```

```json
{
 "set": "set-hark-lantern-3m-hqbn",
 "receipt": "l12 → deadpan, pause 1100 ms, hold 1900 ms, hit \"seven\""
}
```

### 13. `set_set_delivery`

```json
{
 "set": "set-hark-lantern-3m-hqbn",
 "line": "l27",
 "pause_ms": 900,
 "emphasis": [
  "No"
 ]
}
```

```json
{
 "set": "set-hark-lantern-3m-hqbn",
 "receipt": "l27 → deadpan, pause 900 ms, hold 1300 ms, hit \"No\""
}
```

### 14. `set_check_voice`

```json
{
 "set": "set-hark-lantern-3m-hqbn"
}
```

```json
{
 "character": "agent.hark-lantern",
 "score": 1,
 "ok": true,
 "flags": [],
 "checked": 37
}
```

### 15. `set_preview`

```json
{
 "set": "set-hark-lantern-3m-hqbn",
 "event_limit": 12
}
```

Stage timeline: 193s, 12 events shown (first: set.load, set.auto_director, set.camera). Warnings: timings ESTIMATED at 165 wpm for 37/37 lines (no measured words) | cast comic: "agent.hark-lantern" is not a registered identity (inline name used)

### 16. `set_preview`

```json
{
 "set": "set-hark-lantern-3m-hqbn",
 "render": true,
 "clip_seconds": 30
}
```

MP4: `var/characters-previews/set-hark-lantern-3m-hqbn.mp4` (rendered).

### 17. `set_submit`

```json
{
 "set": "set-hark-lantern-3m-hqbn"
}
```

```json
{
 "performance": "set-hark-lantern-3m-hqbn",
 "schema": "funnier.sketch/v1",
 "seconds": 188,
 "beats": 9,
 "play": "/sketch/set-hark-lantern-3m-hqbn",
 "files": [
  "packages/characters/library/hark-lantern/performances/set-hark-lantern-3m-hqbn.sketch.json",
  "apps/live/public/sketches/set-hark-lantern-3m-hqbn.sketch.json",
  "packages/characters/library/hark-lantern/sets/set-hark-lantern-3m-hqbn.json",
  "packages/characters/library/hark-lantern/sets/set-hark-lantern-3m-hqbn.md",
  "packages/characters/library/index.json"
 ]
}
```

### 18. `set_get`

```json
{
 "set": "set-hark-lantern-3m-hqbn"
}
```

Final set: 37 lines, ~186s, status submitted.

### 19. `game_tnts_join`

```json
{
 "character": "hark-lantern",
 "seed": "demo-night"
}
```

Seat seat1 vs Doug Deadline, Madame Chrysalis · winner **pog.doug-deadline** · own lines used 8 · smile breaks 6 (simulated)

First Hark turn: “A quick question arrives at three in the morning.” “It is never quick, and it is barely a question.” “I am a lantern. I am always up. That is the whole design.” “Then: plan my wedding, fix my posture, and tell me if the moon is angry with me.”


## 2. A character the agent chose

### 20. `character_create`

```json
{
 "by": "hark",
 "choose": true,
 "seed": "night-shift-7"
}
```

```json
{
 "id": "agent.static-shelby",
 "name": "Static Shelby",
 "origin": "agent-choice",
 "logline": "Static Shelby: a snail who works as an express courier. Static is unshakeably convinced he is the fastest courier in the city, and perfectionism keeps making it worse.",
 "premise": "A snail who works as an express courier; is unshakeably convinced he is the fastest courier in the city",
 "game": "Static Shelby is unshakeably convinced he is the fastest courier in the city.",
 "want": "to be remembered by name",
 "flaw": "perfectionism: nothing is ever finished, only abandoned",
 "delivery": "warm",
 "catchphrase": "Your parcel is on its way. Spiritually.",
 "glb": {
  "path": "apps/live/public/identities/agent.static-shelby.glb",
  "bytes": 33848,
  "morphs": [
   "jawOpen",
   "mouthSmileLeft",
   "mouthSmileRight",
   "eyeBlinkLeft",
   "eyeBlinkRight"
  ]
 },
 "registered": true,
 "files": [
  "packages/party/identities/agent.static-shelby.json",
  "packages/party/identities/registry.json",
  "apps/live/public/identities/agent.static-shelby.glb",
  "packages/characters/library/static-shelby/theory.json",
  "packages/characters/library/static-shelby/THEORY.md",
  "packages/characters/library/index.json"
 ]
}
```

### 21. `set_write`

```json
{
 "character": "agent.static-shelby",
 "premise": "group chats have too many people and nobody ever leaves",
 "length": 1,
 "seed": "demo-1"
}
```

`set-static-shelby-1m-a2y4` ~59s, voice 1

<details><summary>script</summary>

# Group chats have too many people and nobody ever leaves

Static Shelby · 1-minute set · ~59s (target 60s) · draft · generator: template

Premise: group chats have too many people and nobody ever leaves

## Beat 0: opener

- **OPENER** (l1) Good evening. I am Static Shelby, a snail who works as an express courier.  _[warm]_
- **TAG** (l2) Out for delivery.  _[warm, pause 250, hold 750]_

## Beat 1: bit · delivery · establish

- **SETUP** (l3) I am a courier. Express delivery.  _[deliberate, pause 400]_
- **SETUP** (l4) People see a snail and they make assumptions.  _[deliberate]_
- **PUNCH** (l5) They assume I am slow. I am not slow. I am thorough. I have touched every square centimetre between your house and the depot.  _[deadpan, pause 700, hold 1000, hit: depot]_
- **TAG** (l6) You can see where. It is shiny.  _[warm, pause 250, hold 750]_

## Beat 2: bit · compliments · explore

- **SETUP** (l7) Somebody told me I did a good job today.  _[deliberate, pause 400]_
- **PUNCH** (l8) Good. Not great. Not flawless. Good. I have been up since four rewriting it.  _[deadpan, pause 700, hold 1000, hit: rewriting]_
- **TAG** (l9) I have notes on the compliment. Mostly about pacing.  _[warm, pause 250, hold 750]_

## Beat 3: callback

- **CALLBACK** (l10) Still out for delivery. Follow the shiny line.  _[conspiratorial, pause 600, hold 1000, hit: line]_

## Beat 4: closer

- **CLOSER** (l11) All I want is to be remembered by name. Tonight, I got close. Your parcel is on its way. Spiritually.  _[warm, pause 500, hold 1250]_

</details>


### 22. `set_check_voice`

```json
{
 "set": "set-static-shelby-1m-a2y4"
}
```

```json
{
 "character": "agent.static-shelby",
 "score": 1,
 "ok": true,
 "flags": [],
 "checked": 11
}
```

### 23. `set_submit`

```json
{
 "set": "set-static-shelby-1m-a2y4"
}
```

```json
{
 "performance": "set-static-shelby-1m-a2y4",
 "schema": "funnier.sketch/v1",
 "seconds": 59,
 "beats": 5,
 "play": "/sketch/set-static-shelby-1m-a2y4",
 "files": [
  "packages/characters/library/static-shelby/performances/set-static-shelby-1m-a2y4.sketch.json",
  "apps/live/public/sketches/set-static-shelby-1m-a2y4.sketch.json",
  "packages/characters/library/static-shelby/sets/set-static-shelby-1m-a2y4.json",
  "packages/characters/library/static-shelby/sets/set-static-shelby-1m-a2y4.md",
  "packages/characters/library/index.json"
 ]
}
```

### 24. `game_tnts_join`

```json
{
 "character": "agent.static-shelby",
 "seed": "demo-rematch",
 "opponents": [
  "agent.hark-lantern",
  "pog.the-algorithm"
 ]
}
```

Table: seat1 Static Shelby, seat2 Hark Lantern, seat3 The Algorithm · winner **agent.hark-lantern** · smile breaks 4 (simulated)

### 25. `character_list`

```json
{}
```

```json
{
 "characters": [
  {
   "id": "agent.hark-lantern",
   "name": "Hark Lantern",
   "logline": "A lantern-headed concierge who hears everything and announces it, politely, one beat too late.",
   "origin": "adopted",
   "delivery": "deadpan",
   "sets": 1,
   "appearances": 5
  },
  {
   "id": "agent.static-shelby",
   "name": "Static Shelby",
   "logline": "Static Shelby: a snail who works as an express courier. Static is unshakeably convinced he is the fastest courier in the city, and perfectionism keeps making it worse.",
   "origin": "agent-choice",
   "delivery": "warm",
   "sets": 1,
   "appearances": 2
  }
 ]
}
```
