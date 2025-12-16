<template>
  <div class="page">
    <div class="card">
      <!-- Timer -->
      <div class="timer">00:00</div>

      <!-- Avatar -->
      <div class="avatar">
        <div class="orb"></div>
      </div>

      <!-- Title -->
      <h2 class="title">Eleven</h2>
      <p class="subtitle">Your ElevenLabs assistant</p>

      <!-- Controls -->
      <div class="controls">
        <button class="icon-btn">🇺🇸</button>

        <button
          class="icon-btn mic"
          :class="{ active: recording }"
          :disabled="!connected"
          @mousedown.prevent="startRecording"
          @mouseup.prevent="stopRecording"
          @touchstart.prevent="startRecording"
          @touchend.prevent="stopRecording"
        >
          🎤
        </button>

        <button class="call-btn">📞</button>
      </div>

      <!-- Status -->
      <p class="status-text">
        <span v-if="connected">Connected</span>
        <span v-else>Connecting…</span>
      </p>

      <!-- Transcript -->
      <div class="transcript">
        <p class="user" style="color: black;">{{ currentTurn }}</p>
        <p class="assistant" style="color: black;">{{ assistantText }}</p>
      </div>
    </div>
  </div>
</template>




<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from "vue";

const WS_URL = "ws://localhost:8000/ws/voice";
const userId = "user-123";

/* ---------- STATE ---------- */
const ws = ref<WebSocket | null>(null);
const connected = ref(false);
const recording = ref(false);
const aiSpeaking = ref(false);

const currentTurn = ref("");
const assistantText = ref("");

/* ---------- AUDIO ---------- */
let recordCtx: AudioContext | null = null;
let playCtx: AudioContext | null = null;
let micStream: MediaStream | null = null;
let playTime = 0;

let ttsSampleRate = 24000;

/* ---------- LIFECYCLE ---------- */
onMounted(connectWS);
onBeforeUnmount(cleanup);

/* ---------- WEBSOCKET ---------- */
function connectWS() {
  const socket = new WebSocket(`${WS_URL}?user_id=${userId}`);
  socket.binaryType = "arraybuffer";

  socket.onopen = () => {
    connected.value = true;
    ws.value = socket;
    socket.send(JSON.stringify({ type: "start_session" }));
  };

  socket.onclose = () => {
    connected.value = false;
    ws.value = null;
  };

  socket.onmessage = (e) => {
    if (typeof e.data === "string") {
      const msg = JSON.parse(e.data);

      if (msg.type === "ai_text_delta") {
        currentTurn.value += msg.text || "";
        if (msg.is_final) {
          assistantText.value += currentTurn.value + "\n";
          currentTurn.value = "";
        }
      }

      if (msg.type === "ai_speaking") {
        aiSpeaking.value = msg.value;
      }

      if (msg.type === "sample_rate") {
        ttsSampleRate = msg.tts;
      }
      return;
    }

    playPcm(e.data);
  };
}

/* ---------- RECORDING (AudioWorklet) ---------- */
async function startRecording() {
  if (recording.value) return;

  if (aiSpeaking.value) {
    ws.value?.send(JSON.stringify({ type: "barge_in" }));
    stopPlayback();
  }

  recording.value = true;
  ws.value?.send(JSON.stringify({ type: "start_speaking" }));

  recordCtx = new AudioContext({ sampleRate: 16000 });
  await recordCtx.audioWorklet.addModule("/pcm-processor.js");

  micStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true
    }
  });

  const source = recordCtx.createMediaStreamSource(micStream);
  const worklet = new AudioWorkletNode(recordCtx, "pcm-processor");

  worklet.port.onmessage = (e) => {
    if (!ws.value) return;
    if (ws.value.bufferedAmount < 300_000) {
      ws.value.send(e.data);
    }
  };

  source.connect(worklet);
}

function stopRecording() {
  if (!recording.value) return;
  recording.value = false;

  ws.value?.send(JSON.stringify({ type: "stop_speaking" }));

  micStream?.getTracks().forEach(t => t.stop());
  micStream = null;

  recordCtx?.close();
  recordCtx = null;
}

/* ---------- PLAYBACK ---------- */
function ensurePlayCtx() {
  if (!playCtx) {
    playCtx = new AudioContext();
    playTime = playCtx.currentTime;
  }
}

function playPcm(pcm16: ArrayBuffer) {
  ensurePlayCtx();
  const ctx = playCtx!;

  const samples = resamplePCM16(pcm16, ttsSampleRate, ctx.sampleRate);
  const buffer = ctx.createBuffer(1, samples.length, ctx.sampleRate);
  buffer.getChannelData(0).set(samples);

  const src = ctx.createBufferSource();
  src.buffer = buffer;
  src.connect(ctx.destination);

  playTime = Math.max(playTime, ctx.currentTime + 0.03);
  src.start(playTime);
  playTime += buffer.duration;
}

function stopPlayback() {
  playCtx?.close();
  playCtx = null;
}

/* ---------- HELPERS ---------- */
function resamplePCM16(pcm: ArrayBuffer, srcRate: number, dstRate: number) {
  const input = new Int16Array(pcm);
  const ratio = dstRate / srcRate;
  const out = new Float32Array(Math.floor(input.length * ratio));

  for (let i = 0; i < out.length; i++) {
    const idx = i / ratio;
    const i0 = Math.floor(idx);
    const i1 = Math.min(i0 + 1, input.length - 1);
    const t = idx - i0;
    out[i] = ((1 - t) * input[i0] + t * input[i1]) / 0x8000;
  }
  return out;
}

function cleanup() {
  stopRecording();
  stopPlayback();
  ws.value?.close();
}
</script>

<style scoped>
.voice-chat {
  max-width: 520px;
  margin: 2rem auto;
  padding: 1.5rem;
  border-radius: 1rem;
  border: 1px solid #ddd;
}
.mic-btn {
  padding: 0.7rem 1rem;
  border-radius: 999px;
  border: none;
  background: #2563eb;
  color: white;
}
.transcript {
  margin-top: 1rem;
  background: #f9fafb;
  padding: 1rem;
  border-radius: 0.75rem;
}
.assistant {
  opacity: 0.8;
}

.page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: #f6f7fb;
}

.card {
  width: 360px;
  padding: 2rem 1.5rem;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.08);
  text-align: center;
}

.timer {
  font-size: 14px;
  color: #6b7280;
  margin-bottom: 1rem;
}

/* Avatar */
.avatar {
  display: flex;
  justify-content: center;
  margin-bottom: 1rem;
}

.orb {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: radial-gradient(
    circle at 30% 30%,
    #7dd3fc,
    #2563eb
  );
  animation: spin 6s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.title {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 600;
}

.subtitle {
  margin: 0.25rem 0 1.5rem;
  color: #6b7280;
  font-size: 0.9rem;
}

/* Controls */
.controls {
  display: flex;
  justify-content: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.icon-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: none;
  background: #e5e7eb;
  font-size: 1.2rem;
  cursor: pointer;
}

.mic.active {
  background: #2563eb;
  color: white;
}

.call-btn {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #22c55e;
  border: none;
  font-size: 1.3rem;
  cursor: pointer;
}

.status-text {
  font-size: 0.8rem;
  color: #6b7280;
  margin-bottom: 1rem;
}

/* Transcript */
.transcript {
  background: #f9fafb;
  padding: 0.75rem;
  border-radius: 12px;
  max-height: 120px;
  overflow-y: auto;
  text-align: left;
  font-size: 0.85rem;
}

.user {
  font-weight: 500;
}

.assistant {
  opacity: 0.75;
}

</style>
