/**
 * @freaktown/newsroom — the newsroom SDK.
 *   schema    Sofie-style rundown (show → segment → story → piece) + validator
 *   styles    show styles (goodnight, default-news) + cadence profiles
 *   timing    measured words (words.json) or 105-wpm estimates → program clock
 *   director  BBC-R&D-Ed shot timing/selection + broadcast grammar
 *   compile   rundown + timings → set stage event timeline
 *   wall      procedural wall-card painter (no network)
 * See docs/NEWSROOM-SDK.md.
 */
export * from './schema';
export * from './styles';
export * from './timing';
export * from './director';
export * from './compile';
export * from './wall';
