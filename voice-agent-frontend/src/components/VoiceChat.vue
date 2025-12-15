<template>
  <div class="voice-chat">
    <h2>Voice Agent</h2>

    <div class="status">
      <span v-if="connected">🟢 Connected</span>
      <span v-else>🔴 Connecting...</span>
    </div>

    <button
      class="mic-btn"
      :disabled="!connected"
      @mousedown.prevent="startRecording"
      @mouseup.prevent="stopRecording"
      @touchstart.prevent="startRecording"
      @touchend.prevent="stopRecording"
    >
      <span v-if="!recording">Hold to talk 🎤</span>
      <span v-else>Release to send ⏺</span>
    </button>

    <div class="transcript">
      <p>{{ currentTurn }}</p>
      <p class="assistant">{{ assistantText }}</p>
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
</style>
