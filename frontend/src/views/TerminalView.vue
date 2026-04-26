<template>
  <div class="terminal-view">
    <!-- Top Bar for Terminal -->
    <header class="term-topbar">
      <div class="term-topbar__left">
        <button class="term-btn term-btn--back" @click="router.push('/')">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
          Back
        </button>
        <span class="term-title">SSH Terminal <span class="term-title__code">({{ route.params.code }})</span></span>
      </div>
      <div class="term-topbar__right">
        <span class="term-status">
          <span class="status-dot status-dot--online"></span> Connected
        </span>
      </div>
    </header>

    <!-- Terminal Container -->
    <div class="term-container" ref="terminalContainer"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'

const router = useRouter()
const route = useRoute()
const terminalContainer = ref(null)

let term = null
let fitAddon = null
let resizeObserver = null

onMounted(() => {
  // Initialize xterm.js
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
  
  if (terminalContainer.value) {
    term.open(terminalContainer.value)
    fitAddon.fit()
    
    // Welcome message
    term.writeln('\x1b[1;31mAnyDesk SSH Terminal\x1b[0m')
    term.writeln(`Connecting to Session: \x1b[1;36m${route.params.code}\x1b[0m...`)
    setTimeout(() => {
      term.writeln('\x1b[1;32mConnection established.\x1b[0m')
      term.writeln('Welcome to the remote terminal.')
      term.write('\r\n$ ')
    }, 800)

    // Handle input (mocking local echo for demo)
    term.onData(data => {
      const code = data.charCodeAt(0)
      // Enter
      if (code === 13) {
        term.write('\r\n$ ')
      } else if (code === 127) {
        // Backspace
        term.write('\b \b')
      } else {
        term.write(data)
      }
    })

    // Handle window resize
    resizeObserver = new ResizeObserver(() => {
      fitAddon.fit()
    })
    resizeObserver.observe(terminalContainer.value)
  }
})

onBeforeUnmount(() => {
  if (resizeObserver && terminalContainer.value) {
    resizeObserver.unobserve(terminalContainer.value)
  }
  if (term) {
    term.dispose()
  }
})
</script>

<style scoped>
.terminal-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 42px);
  background: #1e1e1e;
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

.term-topbar__left, .term-topbar__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.term-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: #ccc;
  font-size: 0.85rem;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 150ms;
}

.term-btn:hover {
  background: rgba(255,255,255,0.1);
  color: white;
}

.term-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: white;
}

.term-title__code {
  color: #d32f2f;
  font-family: var(--font-mono);
}

.term-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8rem;
  color: #4caf50;
}

.term-container {
  flex: 1;
  padding: 16px;
  overflow: hidden;
}
</style>
