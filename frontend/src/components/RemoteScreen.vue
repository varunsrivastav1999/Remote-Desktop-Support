<template>
  <div
    class="remote-screen"
    ref="container"
    tabindex="0"
    @mousedown="handleMouse('mousedown', $event)"
    @mouseup="handleMouse('mouseup', $event)"
    @mousemove="handleMouse('mousemove', $event)"
    @click.prevent="handleMouse('click', $event)"
    @dblclick.prevent="handleMouse('dblclick', $event)"
    @contextmenu.prevent="handleMouse('contextmenu', $event)"
    @wheel.prevent="handleWheel"
    @keydown.prevent="handleKey('keydown', $event)"
    @keyup.prevent="handleKey('keyup', $event)"
  >
    <video
      ref="videoEl"
      class="remote-screen__video"
      autoplay
      playsinline
      muted
    ></video>

    <!-- Cursor overlay indicator -->
    <div class="remote-screen__cursor-hint" v-if="showCursorHint">
      Click anywhere to start controlling
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  stream: {
    type: MediaStream,
    default: null,
  },
})

const emit = defineEmits(['mouse-event', 'key-event', 'clipboard-paste'])

const container = ref(null)
const videoEl = ref(null)
const showCursorHint = ref(true)

// Throttle mousemove events to ~60fps
let lastMoveTime = 0
const MOVE_THROTTLE_MS = 16

// Attach the remote stream to the video element
watch(
  () => props.stream,
  (newStream) => {
    if (videoEl.value && newStream) {
      videoEl.value.srcObject = newStream
      videoEl.value.play().catch(e => console.warn('[RemoteScreen] Video play failed:', e))
    }
  },
  { immediate: true }
)

onMounted(() => {
  // Focus the container to capture keyboard events
  container.value?.focus()
})

onUnmounted(() => {
  if (videoEl.value) {
    videoEl.value.srcObject = null
  }
})

/**
 * Convert mouse event to relative coordinates and emit.
 */
function handleMouse(type, event) {
  showCursorHint.value = false

  // Throttle mousemove
  if (type === 'mousemove') {
    const now = performance.now()
    if (now - lastMoveTime < MOVE_THROTTLE_MS) return
    lastMoveTime = now
  }

  const rect = videoEl.value?.getBoundingClientRect()
  if (!rect) return

  const x = (event.clientX - rect.left) / rect.width
  const y = (event.clientY - rect.top) / rect.height

  // Clamp to 0-1 range
  const clampedX = Math.max(0, Math.min(1, x))
  const clampedY = Math.max(0, Math.min(1, y))

  emit('mouse-event', {
    type,
    x: clampedX,
    y: clampedY,
    extra: {
      button: event.button,
    },
  })
}

/**
 * Handle scroll/wheel events.
 */
function handleWheel(event) {
  const rect = videoEl.value?.getBoundingClientRect()
  if (!rect) return

  const x = (event.clientX - rect.left) / rect.width
  const y = (event.clientY - rect.top) / rect.height

  emit('mouse-event', {
    type: 'scroll',
    x: Math.max(0, Math.min(1, x)),
    y: Math.max(0, Math.min(1, y)),
    extra: {
      deltaX: event.deltaX,
      deltaY: event.deltaY,
    },
  })
}

/**
 * Handle keyboard events.
 * Intercepts Ctrl+V to sync clipboard to host.
 */
function handleKey(type, event) {
  // Intercept Ctrl+V / Cmd+V to sync clipboard
  if (type === 'keydown' && event.key === 'v' && (event.ctrlKey || event.metaKey)) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.readText().then(text => {
        if (text) {
          emit('clipboard-paste', text)
        }
      }).catch(() => {})
    }
  }

  emit('key-event', {
    type,
    key: event.key,
    modifiers: {
      ctrl: event.ctrlKey,
      shift: event.shiftKey,
      alt: event.altKey,
      meta: event.metaKey,
    },
  })
}
</script>

<style scoped>
.remote-screen {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  cursor: crosshair;
  outline: none;
  position: relative;
  overflow: hidden;
}

.remote-screen__video {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.remote-screen__cursor-hint {
  position: absolute;
  bottom: var(--space-xl);
  left: 50%;
  transform: translateX(-50%);
  padding: var(--space-sm) var(--space-lg);
  font-size: 0.85rem;
  color: var(--color-text-secondary);
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border: 1px solid var(--glass-border);
  border-radius: var(--border-radius-full);
  pointer-events: none;
  animation: fade-in 0.5s ease-out, pulse-amber 2s ease-in-out infinite;
  white-space: nowrap;
}
</style>
