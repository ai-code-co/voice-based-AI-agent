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
      @mousedown="startRecording"
      @mouseup="stopRecording"
      @touchstart.prevent="startRecording"
      @touchend.prevent="stopRecording"
    >
      <span v-if="!isRecording">Hold to talk 🎤</span>
      <span v-else>Release to send ⏺</span>
    </button>

    <div class="transcript">
      <h3>Assistant says:</h3>
      <p>{{ assistantText }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from "vue";

const userId = "user-123"; // replace with real user id / auth

const ws = ref<WebSocket | null>(null);
const connected = ref(false);
const isRecording = ref(false);
const assistantText = ref("");

let audioCtx: AudioContext | null = null;
let processor: ScriptProcessorNode | null = null;
let sourceNode: MediaStreamAudioSourceNode | null = null;
let mediaStream: MediaStream | null = null;

const SAMPLE_RATE = 16000; // must match what you configured in Realtime
const BACKEND_WS_URL = "ws://localhost:8000/ws/voice"; // change for prod

onMounted(() => {
  connectWebSocket();
});

onBeforeUnmount(() => {
  cleanupAudio();
  if (ws.value && ws.value.readyState === WebSocket.OPEN) {
    ws.value.close();
  }
});

function connectWebSocket() {
  const url = `${BACKEND_WS_URL}?user_id=${encodeURIComponent(userId)}`;
  const socket = new WebSocket(url);
  socket.binaryType = "arraybuffer";

  socket.onopen = () => {
    connected.value = true;
    ws.value = socket;
    socket.send(JSON.stringify({ type: "start_session" }));
  };

  socket.onclose = () => {
    connected.value = false;
  };

  socket.onerror = (e) => {
    console.error("WS error", e);
  };

  socket.onmessage = (event) => {
    if (typeof event.data === "string") {
      const msg = JSON.parse(event.data);
      if (msg.type === "ready") {
        console.log("Backend ready");
      } else if (msg.type === "ai_text_delta") {
        if (msg.is_final) {
          // nothing special here, but you could mark end of sentence
        } else if (msg.text) {
          assistantText.value += msg.text;
        }
      }
    } else {
      // binary audio chunk from backend
      const buffer = event.data as ArrayBuffer;
      playPcmChunk(buffer);
    }
  };
}

async function startRecording() {
  if (!connected.value || isRecording.value) return;

  isRecording.value = true;

  if (!audioCtx) {
    audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
  }

  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });

  sourceNode = audioCtx.createMediaStreamSource(mediaStream);

  processor = audioCtx.createScriptProcessor(4096, 1, 1);
  sourceNode.connect(processor);
  processor.connect(audioCtx.destination);

  processor.onaudioprocess = (e: AudioProcessingEvent) => {
    const input = e.inputBuffer.getChannelData(0); // Float32[-1,1]
    const pcm = float32ToPCM16(input);
    ws.value?.send(pcm); // send raw PCM bytes
  };
}

function stopRecording() {
  if (!isRecording.value) return;
  isRecording.value = false;
  cleanupAudio();

  // Tell backend this utterance is done
  ws.value?.send(JSON.stringify({ type: "stop_speaking" }));
}

function cleanupAudio() {
  if (processor) {
    processor.disconnect();
    processor.onaudioprocess = null;
    processor = null;
  }
  if (sourceNode) {
    sourceNode.disconnect();
    sourceNode = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop());
    mediaStream = null;
  }
}

function float32ToPCM16(float32Array: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(float32Array.length * 2);
  const view = new DataView(buffer);
  let offset = 0;
  for (let i = 0; i < float32Array.length; i++, offset += 2) {
    let s = Math.max(-1, Math.min(1, float32Array[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

function playPcmChunk(chunk: ArrayBuffer) {
  if (!audioCtx) {
    audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
  }
  const ctx = audioCtx;

  const int16 = new Int16Array(chunk);
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) {
    float32[i] = int16[i] / 0x8000;
  }

  const audioBuffer = ctx.createBuffer(1, float32.length, SAMPLE_RATE);
  audioBuffer.getChannelData(0).set(float32);

  const src = ctx.createBufferSource();
  src.buffer = audioBuffer;
  src.connect(ctx.destination);
  src.start();
}
</script>

<style scoped>
.voice-chat {
  max-width: 400px;
  margin: 2rem auto;
  padding: 1rem 1.5rem;
  border-radius: 1rem;
  border: 1px solid #ddd;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.mic-btn {
  margin: 1rem 0;
  padding: 1rem 1.5rem;
  border-radius: 999px;
  border: none;
  background: #2563eb;
  color: white;
  font-size: 1rem;
  cursor: pointer;
}
.mic-btn:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}
.status {
  font-size: 0.9rem;
  color: #4b5563;
}
.transcript {
  margin-top: 1rem;
  min-height: 4rem;
  border-radius: 0.75rem;
  background: #f9fafb;
  padding: 0.75rem;
  font-size: 0.95rem;
}
</style>
