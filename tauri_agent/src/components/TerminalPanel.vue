<template>
  <transition name="slide">
    <div v-if="visible" class="terminal-panel">
      <header class="term-topbar">
        <span class="term-title">SSH Terminal</span>
        <button class="term-btn-close" @click="$emit('close')">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </header>
      <div class="term-container" ref="terminalContainer"></div>
    </div>
  </transition>
</template>

<script setup>
import { ref, watch, onBeforeUnmount, nextTick } from 'vue'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'

const props = defineProps({
  visible: Boolean,
  webrtc: Object
})

const emit = defineEmits(['close'])

const terminalContainer = ref(null)
let term = null
let fitAddon = null
let resizeObserver = null

watch(() => props.visible, async (isVisible) => {
  if (isVisible) {
    await nextTick()
    if (!term && terminalContainer.value) {
      initTerminal()
    } else if (term) {
      fitAddon.fit()
    }
    nextTick(() => term?.focus())
  }
})

function initTerminal() {
  term = new Terminal({
    cursorBlink: true,
    fontFamily: '"Fira Code", "Courier New", monospace',
    fontSize: 14,
    theme: {
      background: '#1e1e1e',
      foreground: '#d4d4d4',
      cursor: '#d32f2f',
      selectionBackground: 'rgba(211, 47, 47, 0.3)'
    }
  })

  fitAddon = new FitAddon()
  term.loadAddon(fitAddon)
  term.open(terminalContainer.value)
  fitAddon.fit()

  term.writeln('\x1b[1;32mConnected to Remote Shell.\x1b[0m')

  // Send input to host
  term.onData(data => {
    if (props.webrtc) {
      props.webrtc.sendTerminalData(data)
    }
  })

  // Handle resize
  resizeObserver = new ResizeObserver(() => {
    fitAddon.fit()
  })
  resizeObserver.observe(terminalContainer.value)
}

// Receive output from host
watch(() => props.webrtc, (webrtcObj) => {
  if (webrtcObj) {
    webrtcObj.setTerminalCallback((data) => {
      if (term) term.write(data)
    })
  }
}, { immediate: true })

onBeforeUnmount(() => {
  if (resizeObserver && terminalContainer.value) {
    resizeObserver.unobserve(terminalContainer.value)
  }
  if (term) {
    term.dispose()
    term = null
  }
})
</script>

<style scoped>
.terminal-panel {
  position: absolute;
  top: 0;
  bottom: 0;
  right: 0;
  width: 600px;
  max-width: 100%;
  background: #1e1e1e;
  border-left: 1px solid #333;
  display: flex;
  flex-direction: column;
  z-index: 40;
  box-shadow: -4px 0 16px rgba(0,0,0,0.5);
}

.slide-enter-active, .slide-leave-active {
  transition: transform 0.3s ease;
}
.slide-enter-from, .slide-leave-to {
  transform: translateX(100%);
}

.term-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #252526;
  border-bottom: 1px solid #333;
  flex-shrink: 0;
}

.term-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: white;
}

.term-btn-close {
  background: none;
  border: none;
  color: #ccc;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
}

.term-btn-close:hover {
  background: rgba(255,255,255,0.1);
  color: white;
}

.term-container {
  flex: 1;
  padding: 16px;
  overflow: hidden;
}
</style>
