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
      <p style="color: black;">{{ currentTurn }}</p>
      <p style="color: black;">{{ assistantText }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from "vue";

/* -------------------- STATE -------------------- */
const BACKEND_WS_URL = "ws://localhost:8000/ws/voice";
const userId = "user-123";

const ws = ref<WebSocket | null>(null);
const connected = ref(false);
const recording = ref(false);

const currentTurn = ref("");
const assistantText = ref("");

/* -------------------- AUDIO -------------------- */
let recordCtx: AudioContext | null = null;
let playCtx: AudioContext | null = null;

let micStream: MediaStream | null = null;
let sourceNode: MediaStreamAudioSourceNode | null = null;
let processor: ScriptProcessorNode | null = null;

let playTime = 0;

/* -------------------- LIFECYCLE -------------------- */
onMounted(connectWS);
onBeforeUnmount(cleanupAll);

/* -------------------- WEBSOCKET -------------------- */
function connectWS() {
  const socket = new WebSocket(`${BACKEND_WS_URL}?user_id=${userId}`);
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

  socket.onmessage = (event) => {
    if (typeof event.data === "string") {
      const msg = JSON.parse(event.data);
      if (msg.type === "ai_text_delta") {
        if (msg.text) currentTurn.value += msg.text;
        if (msg.is_final) {
          assistantText.value += currentTurn.value + "\n";
          currentTurn.value = "";
        }
      }
      return;
    }
    playPcm(event.data);
  };
}

/* -------------------- RECORDING -------------------- */
async function startRecording() {
  if (recording.value) return;
  recording.value = true;

  recordCtx = new AudioContext();
  micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  sourceNode = recordCtx.createMediaStreamSource(micStream);

  processor = recordCtx.createScriptProcessor(2048, 1, 1);
  sourceNode.connect(processor);

  const silent = recordCtx.createGain();
  silent.gain.value = 0;
  processor.connect(silent);
  silent.connect(recordCtx.destination);

  processor.onaudioprocess = (e) => {
    const pcm = floatToPCM16(e.inputBuffer.getChannelData(0), 0.8);
    ws.value?.send(pcm);
  };
}

function stopRecording() {
  if (!recording.value) return;
  recording.value = false;

  ws.value?.send(JSON.stringify({ type: "stop_speaking" }));

  processor?.disconnect();
  processor = null;

  sourceNode?.disconnect();
  sourceNode = null;

  micStream?.getTracks().forEach(t => t.stop());
  micStream = null;

  recordCtx?.close();
  recordCtx = null;
}

/* -------------------- PLAYBACK -------------------- */
function ensurePlayCtx() {
  if (!playCtx) {
    playCtx = new AudioContext(); // native (48kHz)
    playTime = playCtx.currentTime;
  }
}

function playPcm(pcm16: ArrayBuffer) {
  ensurePlayCtx();
  const ctx = playCtx!;

  const samples = resamplePCM16(pcm16, 16000, ctx.sampleRate);
  const buffer = ctx.createBuffer(1, samples.length, ctx.sampleRate);
  buffer.getChannelData(0).set(samples);

  const src = ctx.createBufferSource();
  src.buffer = buffer;
  src.connect(ctx.destination);

  const SAFETY = 0.03;
  if (playTime < ctx.currentTime + SAFETY) {
    playTime = ctx.currentTime + SAFETY;
  }

  src.start(playTime);
  playTime += buffer.duration;

  src.onended = () => src.disconnect();
}

/* -------------------- HELPERS -------------------- */
function floatToPCM16(input: Float32Array, gain = 1) {
  const buf = new ArrayBuffer(input.length * 2);
  const view = new DataView(buf);
  for (let i = 0; i < input.length; i++) {
    let s = Math.max(-1, Math.min(1, input[i] * gain));
    view.setInt16(i * 2, s * 0x7fff, true);
  }
  return buf;
}

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

function cleanupAll() {
  stopRecording();
  playCtx?.close();
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
  cursor: pointer;
}
.transcript {
  margin-top: 1rem;
  background: #f9fafb;
  padding: 1rem;
  border-radius: 0.75rem;
}
</style>