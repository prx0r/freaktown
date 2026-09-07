# Freak Town iOS shell (Capacitor 8)

Live-URL mode: the app loads `https://freaktown.egoic.ai`, so the web
build is always current. No Swift, no React Native, no fork.

## Prereqs (Mac only)

- Xcode 15+, CocoaPods
- Node 20+

## Build

```bash
cd app-shell
npm install
npx cap add ios
npx cap sync
npx cap open ios
```

Then archive in Xcode as usual.

## Native features (already guarded in editor.html)

| Feature | Plugin | Web fallback |
|---------|--------|--------------|
| Haptics on split/save/slide | @capacitor/haptics | navigator.vibrate |
| Share clip link | @capacitor/share | navigator.share → clipboard |
| Mic capture for voice cloning | @capacitor/voice-recorder | (web: skip) |
| Bundle export to Files | @capacitor/filesystem | JSON download |
| Show-night push | @capacitor/push-notifications | (web: none) |

The editor probes `window.Capacitor.Plugins.*` and degrades gracefully,
so the same page runs in Safari, PWA, and the shell.

## App Store note

Apple rejects dumb WebView wrappers. Our native surface: haptics,
mic capture, share sheet, filesystem export, push. Keep all five
wired before submitting.

## PWA (no Mac needed)

The site is installable today: manifest + service worker + icons
ship from `/`. Add to Home Screen on iPhone for the standalone build.
