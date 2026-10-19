<template>
  <div
    class="remote-screen"
    ref="container"
    tabindex="0"
    @mousedown="handleMouse('mousedown', $event)"
    @mouseup="handleMouse('mouseup', $event)"
    @mousemove="handleMouse('mousemove', $event)"
    @dblclick.prevent="handleMouse('dblclick', $event)"
    @contextmenu.prevent="handleMouse('contextmenu', $event)"
    @wheel.prevent="handleWheel"
    @keydown.prevent="handleKey('keydown', $event)"
    @keyup.prevent="handleKey('keyup', $event)"
    @mouseleave="pointerPos.visible = false"
  >
    <video
      ref="videoEl"
      class="remote-screen__video"
      autoplay
      playsinline
      muted
      @loadedmetadata="onLoadedMetadata"
      @canplay="onCanPlay"
    ></video>

    <!-- Real-time controller pointer indicator -->
    <div
      v-if="pointerPos.visible"
      :class="['remote-pointer-marker', { 'remote-pointer-marker--clicking': pointerPos.clicking }]"
      :style="{ left: pointerPos.x + 'px', top: pointerPos.y + 'px' }"
    ></div>

    <!-- Cursor overlay indicator -->
    <div class="remote-screen__cursor-hint" v-if="showCursorHint">
      Click anywhere to start controlling
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, onUnmounted, nextTick } from 'vue'

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

const pointerPos = reactive({
  x: 0,
  y: 0,
  visible: false,
  clicking: false,
})

// Throttle mousemove events to ~60fps
let lastMoveTime = 0
const MOVE_THROTTLE_MS = 16

function attachStream(stream) {
  if (!videoEl.value) return
  try {
    videoEl.value.muted = true
    if (videoEl.value.srcObject !== stream) {
      console.log('[RemoteScreen] Attaching remote stream:', stream)
      videoEl.value.srcObject = stream || null
    }
    if (stream) {
      stream.getVideoTracks().forEach(track => {
        track.enabled = true
        track.onunmute = () => {
          console.log('[RemoteScreen] Remote video track unmuted')
          if (videoEl.value) {
            videoEl.value.play().catch(e => console.warn('[RemoteScreen] Play on unmute:', e))
          }
        }
      })
      const p = videoEl.value.play()
      if (p !== undefined) {
        p.catch(e => console.warn('[RemoteScreen] Video play failed:', e))
      }
    }
  } catch (err) {
    console.error('[RemoteScreen] Error attaching stream:', err)
  }
}

function onLoadedMetadata() {
  console.log('[RemoteScreen] Video metadata loaded:', videoEl.value?.videoWidth, 'x', videoEl.value?.videoHeight)
  if (videoEl.value) {
    videoEl.value.play().catch(e => console.warn('[RemoteScreen] Play on loadedmetadata:', e))
  }
}

function onCanPlay() {
  if (videoEl.value) {
    videoEl.value.play().catch(e => console.warn('[RemoteScreen] Play on canplay:', e))
  }
}

// Attach remote stream whenever it changes
watch(
  () => props.stream,
  (newStream) => {
    attachStream(newStream)
  }
)

onMounted(() => {
  attachStream(props.stream)
  nextTick(() => {
    attachStream(props.stream)
  })
  container.value?.focus()
})

onUnmounted(() => {
  if (videoEl.value) {
    videoEl.value.srcObject = null
  }
})

/**
 * Calculates normalized coordinates (0..1) accounting for CSS object-fit: contain letterboxing.
 */
function getRelativeCoordinates(event) {
  const video = videoEl.value
  if (!video) return null
  const rect = video.getBoundingClientRect()
  if (!rect.width || !rect.height) return null

  const videoWidth = video.videoWidth || rect.width
  const videoHeight = video.videoHeight || rect.height

  const videoRatio = videoWidth / videoHeight
  const elemRatio = rect.width / rect.height

  let renderedWidth = rect.width
  let renderedHeight = rect.height
  let offsetX = 0
  let offsetY = 0

  if (videoRatio > elemRatio) {
    renderedHeight = rect.width / videoRatio
    offsetY = (rect.height - renderedHeight) / 2
  } else {
    renderedWidth = rect.height * videoRatio
    offsetX = (rect.width - renderedWidth) / 2
  }

  const clientX = event.clientX
  const clientY = event.clientY

  const x = (clientX - rect.left - offsetX) / renderedWidth
  const y = (clientY - rect.top - offsetY) / renderedHeight

  return {
    x: Math.max(0, Math.min(1, x)),
    y: Math.max(0, Math.min(1, y)),
  }
}

/**
 * Convert mouse event to relative coordinates and emit.
 */
function handleMouse(type, event) {
  showCursorHint.value = false
  container.value?.focus()

  // Track pointer marker position relative to container
  if (container.value) {
    const cRect = container.value.getBoundingClientRect()
    pointerPos.x = event.clientX - cRect.left
    pointerPos.y = event.clientY - cRect.top
    pointerPos.visible = true
    if (type === 'mousedown') pointerPos.clicking = true
    if (type === 'mouseup') pointerPos.clicking = false
  }

  // Throttle mousemove
  if (type === 'mousemove') {
    const now = performance.now()
    if (now - lastMoveTime < MOVE_THROTTLE_MS) return
    lastMoveTime = now
  }

  const coords = getRelativeCoordinates(event)
  if (!coords) return

  let btn = event.button
  if (type === 'contextmenu') {
    btn = 2
  }

  emit('mouse-event', {
    type,
    x: coords.x,
    y: coords.y,
    extra: {
      button: btn,
    },
  })
}

/**
 * Handle scroll/wheel events.
 */
function handleWheel(event) {
  const coords = getRelativeCoordinates(event)
  if (!coords) return

  emit('mouse-event', {
    type: 'scroll',
    x: coords.x,
    y: coords.y,
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
  cursor: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24'%3E%3Cpath fill='%23ffffff' stroke='%23000000' stroke-width='1.5' stroke-linejoin='round' d='M3 3l7.5 18 2.5-6.5L19.5 12z'/%3E%3C/svg%3E") 0 0, default;
  outline: none;
  position: relative;
  overflow: hidden;
  user-select: none;
}

.remote-screen__video {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.remote-pointer-marker {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.95);
  background: rgba(245, 124, 0, 0.5);
  box-shadow: 0 0 6px rgba(245, 124, 0, 0.9), 0 0 2px #000;
  transform: translate(-50%, -50%);
  pointer-events: none;
  z-index: 30;
  transition: width 0.1s ease, height 0.1s ease, background-color 0.1s ease;
}

.remote-pointer-marker--clicking {
  width: 18px;
  height: 18px;
  background: rgba(245, 124, 0, 0.9);
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
