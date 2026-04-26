<template>
  <transition name="chat-slide">
    <div v-if="visible" class="chat-panel">
      <div class="chat-header">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span>Session Chat</span>
        <button class="chat-close" @click="$emit('close')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      <div class="chat-messages" ref="messagesContainer">
        <div v-if="messages.length === 0" class="chat-empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <p>No messages yet</p>
          <p class="chat-empty__hint">Send a message to the remote host</p>
        </div>
        <div
          v-for="(msg, i) in messages"
          :key="i"
          :class="['chat-msg', msg.sender === 'client' ? 'chat-msg--self' : 'chat-msg--peer']"
        >
          <div class="chat-msg__bubble">
            <p class="chat-msg__text">{{ msg.text }}</p>
            <span class="chat-msg__time">{{ formatTime(msg.timestamp) }}</span>
          </div>
        </div>
      </div>

      <div class="chat-input-row">
        <input
          ref="chatInput"
          v-model="inputText"
          class="chat-input"
          placeholder="Type a message..."
          @keydown.enter="sendMessage"
          maxlength="2000"
        />
        <button class="chat-send" @click="sendMessage" :disabled="!inputText.trim()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  messages: { type: Array, default: () => [] },
})

const emit = defineEmits(['close', 'send'])

const inputText = ref('')
const messagesContainer = ref(null)
const chatInput = ref(null)

function sendMessage() {
  if (!inputText.value.trim()) return
  emit('send', inputText.value.trim())
  inputText.value = ''
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// Auto-scroll to bottom when new messages arrive
watch(() => props.messages.length, () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
})

// Focus input when panel opens
watch(() => props.visible, (v) => {
  if (v) {
    nextTick(() => chatInput.value?.focus())
  }
})
</script>

<style scoped>
.chat-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: 320px;
  height: 100%;
  background: rgba(20, 20, 20, 0.95);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-left: 1px solid rgba(255,255,255,0.08);
  display: flex;
  flex-direction: column;
  z-index: 40;
  box-shadow: -4px 0 24px rgba(0,0,0,0.3);
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  font-weight: 600;
  font-size: 0.85rem;
  color: white;
  flex-shrink: 0;
}

.chat-close {
  margin-left: auto;
  background: none;
  border: none;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  padding: 4px;
  display: flex;
  border-radius: 4px;
  transition: 150ms;
}
.chat-close:hover { color: white; background: rgba(255,255,255,0.1); }

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: rgba(255,255,255,0.3);
  font-size: 0.85rem;
}
.chat-empty__hint { font-size: 0.72rem; opacity: 0.6; }

.chat-msg {
  display: flex;
  max-width: 85%;
}

.chat-msg--self {
  align-self: flex-end;
}
.chat-msg--peer {
  align-self: flex-start;
}

.chat-msg__bubble {
  padding: 8px 12px;
  border-radius: 12px;
  max-width: 100%;
}

.chat-msg--self .chat-msg__bubble {
  background: #d32f2f;
  color: white;
  border-bottom-right-radius: 4px;
}

.chat-msg--peer .chat-msg__bubble {
  background: rgba(255,255,255,0.1);
  color: #e0e0e0;
  border-bottom-left-radius: 4px;
}

.chat-msg__text {
  font-size: 0.82rem;
  line-height: 1.4;
  word-break: break-word;
  margin: 0;
}

.chat-msg__time {
  font-size: 0.6rem;
  opacity: 0.5;
  display: block;
  margin-top: 4px;
  text-align: right;
}

.chat-input-row {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid rgba(255,255,255,0.08);
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
  padding: 8px 12px;
  font-size: 0.82rem;
  background: rgba(255,255,255,0.06);
  color: white;
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 20px;
  outline: none;
  transition: 150ms;
}
.chat-input::placeholder { color: rgba(255,255,255,0.3); }
.chat-input:focus { border-color: #d32f2f; }

.chat-send {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #d32f2f;
  border: none;
  border-radius: 50%;
  color: white;
  cursor: pointer;
  flex-shrink: 0;
  transition: 150ms;
}
.chat-send:hover:not(:disabled) { background: #b71c1c; }
.chat-send:disabled { opacity: 0.3; cursor: not-allowed; }

.chat-slide-enter-active { animation: slide-right 0.25s ease-out; }
.chat-slide-leave-active { animation: slide-right 0.2s ease-in reverse; }
@keyframes slide-right { from { opacity:0; transform:translateX(20px); } to { opacity:1; transform:translateX(0); } }
</style>
