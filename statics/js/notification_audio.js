/*
 * notification_audio.js
 * Plays a more noticeable alert (ring/voice) when the app receives:
 *  - Emergency/ICU patients (IPD category=ICU)
 *  - New notifications of type pharmacy_low/prescription_required/general
 *
 * Uses WebAudio for reliability (no external audio files needed).
 */

(function () {
  'use strict';

  function canUseAudio() {
    return typeof window !== 'undefined' && (window.AudioContext || window.webkitAudioContext);
  }

  function makeBeepPlayer() {
    var AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor) return null;

    var ctx = null;
    function ensureCtx() {
      if (ctx) return ctx;
      ctx = new AudioContextCtor();
      return ctx;
    }

    function beep(freq, durationMs, volume) {
      volume = typeof volume === 'number' ? volume : 0.12;
      var c = ensureCtx();

      var oscillator = c.createOscillator();
      var gainNode = c.createGain();

      oscillator.type = 'sine';
      oscillator.frequency.value = freq;

      gainNode.gain.value = volume;

      oscillator.connect(gainNode);
      gainNode.connect(c.destination);

      var now = c.currentTime;
      var durationSec = durationMs / 1000;
      oscillator.start(now);
      oscillator.stop(now + durationSec);
    }

    // "Ring": quick repeated beeps
    function ring(times, baseFreq) {
      times = typeof times === 'number' ? times : 6;
      baseFreq = typeof baseFreq === 'number' ? baseFreq : 880;

      // Some browsers require resume after a user gesture.
      // If suspended, ignore; next interaction can try again.
      var c = ctx;
      if (c && c.state === 'suspended' && c.resume) {
        try { c.resume(); } catch (e) {}
      }

      for (var i = 0; i < times; i++) {
        (function (idx) {
          setTimeout(function () {
            // Alternate frequency for a more recognizable pattern
            var f = baseFreq + (idx % 2 === 0 ? 0 : 220);
            beep(f, 140, 0.14);
          }, idx * 170);
        })(i);
      }
    }

    // "Voice-like": use SpeechSynthesis when available
    function speak(text) {
      try {
        if (!('speechSynthesis' in window)) return false;
        var u = new SpeechSynthesisUtterance(text);
        u.rate = 1.0;
        u.pitch = 1.1;
        u.volume = 1.0;
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(u);
        return true;
      } catch (e) {
        return false;
      }
    }

    return {
      ring: ring,
      speak: speak,
      beep: beep,
    };
  }

  var audio = null;
  var lastTriggerAt = 0;
  var minIntervalMs = 8000; // throttle to avoid constant beeping

  function triggerAlert(kind, title, message) {
    var now = Date.now();
    if (now - lastTriggerAt < minIntervalMs) return;
    lastTriggerAt = now;

    if (!canUseAudio()) return;
    if (!audio) audio = makeBeepPlayer();
    if (!audio) return;

    // Prefer voice for emergency/ICU; fallback to ring
    if (kind === 'icu' || kind === 'emergency') {
      var voiceText = 'Emergency. ' + (title ? title : 'New ICU admission');
      var usedVoice = audio.speak(voiceText);
      if (!usedVoice) audio.ring(8, 980);
    } else {
      audio.ring(6, 740);
    }
  }

  // Expose to other scripts
  window.HMS_ALERTS = {
    triggerAlert: function (kind, title, message) {
      triggerAlert(kind, title, message);
    },
  };


})();


