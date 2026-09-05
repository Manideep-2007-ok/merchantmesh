/**
 * MerchantMesh — Web Audio API Synthesizer
 * Zero external MP3/WAV dependencies. Generates pristine, low-latency synthesized
 * audio feedback directly via the browser's native AudioContext.
 */

let audioCtx = null;

function getAudioContext() {
  if (typeof window === 'undefined') return null;
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {});
  }
  return audioCtx;
}

export function isSoundEnabled() {
  if (typeof window === 'undefined') return true;
  const stored = localStorage.getItem('mm_sound_enabled');
  return stored === null ? true : stored === 'true';
}

export function setSoundEnabled(enabled) {
  if (typeof window === 'undefined') return;
  localStorage.setItem('mm_sound_enabled', String(enabled));
}

export function toggleSound() {
  const current = isSoundEnabled();
  setSoundEnabled(!current);
  if (!current) {
    playMessagePop();
  }
  return !current;
}

export function playMessagePop() {
  if (!isSoundEnabled()) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(320, now);
    osc.frequency.exponentialRampToValueAtTime(740, now + 0.04);
    gain.gain.setValueAtTime(0.12, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.06);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.07);
  } catch (e) {}
}

export function playTensionPing() {
  if (!isSoundEnabled()) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const osc1 = ctx.createOscillator();
    const osc2 = ctx.createOscillator();
    const gain = ctx.createGain();
    osc1.type = 'triangle'; osc1.frequency.setValueAtTime(880, now);
    osc2.type = 'sine'; osc2.frequency.setValueAtTime(1320, now);
    gain.gain.setValueAtTime(0.15, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
    osc1.connect(gain); osc2.connect(gain);
    gain.connect(ctx.destination);
    osc1.start(now); osc2.start(now);
    osc1.stop(now + 0.19); osc2.stop(now + 0.19);
  } catch (e) {}
}

export function playDealChime() {
  if (!isSoundEnabled()) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const notes = [523.25, 659.25, 783.99, 1046.50];
    notes.forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, now + idx * 0.06);
      gain.gain.setValueAtTime(0.0, now + idx * 0.06);
      gain.gain.linearRampToValueAtTime(0.14, now + idx * 0.06 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.06 + 0.45);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now + idx * 0.06);
      osc.stop(now + idx * 0.06 + 0.5);
    });
  } catch (e) {}
}

export function playPaymentSuccess() {
  if (!isSoundEnabled()) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.type = 'sine'; osc1.frequency.setValueAtTime(783.99, now);
    gain1.gain.setValueAtTime(0.18, now); gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
    osc1.connect(gain1); gain1.connect(ctx.destination);
    osc1.start(now); osc1.stop(now + 0.16);

    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.type = 'sine'; osc2.frequency.setValueAtTime(1046.50, now + 0.12);
    gain2.gain.setValueAtTime(0.22, now + 0.12); gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.48);
    osc2.connect(gain2); gain2.connect(ctx.destination);
    osc2.start(now + 0.12); osc2.stop(now + 0.50);
  } catch (e) {}
}

export function playGuardrailThud() {
  if (!isSoundEnabled()) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'triangle'; osc.frequency.setValueAtTime(130, now);
    osc.frequency.exponentialRampToValueAtTime(45, now + 0.12);
    gain.gain.setValueAtTime(0.20, now); gain.gain.exponentialRampToValueAtTime(0.001, now + 0.14);
    osc.connect(gain); gain.connect(ctx.destination);
    osc.start(now); osc.stop(now + 0.15);
  } catch (e) {}
}
