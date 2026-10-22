# @funnier/newsroom

Newsroom SDK. It turns a Sofie-style rundown (show → segment → story → piece) into a
directed news-studio show:

* show styles (`goodnight` calm, `default-news` brisk)
* a camera director using BBC R&D Ed timing plus broadcast grammar
* measured words (words.json) or 105-wpm estimates (flagged)
* `compile()` → set stage events
* procedural wall cards
* a headless MP4 render CLI

Guide: [`docs/NEWSROOM-SDK.md`](../../docs/NEWSROOM-SDK.md).

```bash
npx vitest run packages/newsroom
CHROMIUM_PATH=/usr/bin/chromium node packages/newsroom/cli/render.mjs rundown.json -o show.mp4 [--words words.json] [--audio a.wav]
```
