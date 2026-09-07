import type { CapacitorConfig } from '@capacitor/cli';

// v1: live-URL mode — the app is the Black Room, always current.
// Native value-add (for App Store review): haptics on split/slide,
// mic capture for voice cloning, share sheet, filesystem export,
// push for show nights. Web fallback paths already in editor.html.
const config: CapacitorConfig = {
  appId: 'town.freak.blackroom',
  appName: 'Freak Town',
  webDir: 'www',
  server: {
    url: 'https://freaktown.egoic.ai',
    cleartext: false,
  },
  ios: {
    contentInset: 'always',
  },
  plugins: {
    PushNotifications: {
      presentationOptions: ['badge', 'sound', 'alert'],
    },
  },
};

export default config;
