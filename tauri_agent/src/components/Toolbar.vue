<template>
  <div class="toolbar">
    <div class="toolbar__left">
      <!-- 🖥️ Connection status -->
      <span class="toolbar__status" title="Connection status">
        <svg class="toolbar__screen-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="2" y="3" width="20" height="14" rx="2"/>
          <line x1="8" y1="21" x2="16" y2="21"/>
          <line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
        <span class="status-dot" :class="statusDotClass"></span>
        <span class="toolbar__status-text">{{ statusLabel }}</span>
      </span>

      <span class="toolbar__sep"></span>

      <!-- Device / Session Code -->
      <span class="toolbar__code font-mono" title="Remote Device ID">{{ sessionCode }}</span>
      <span v-if="hostInfo" class="toolbar__host" title="Connected Hostname">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="2" y="3" width="20" height="14" rx="2"/>
          <line x1="8" y1="21" x2="16" y2="21"/>
          <line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
        {{ hostInfo.hostname }}
      </span>

      <span class="toolbar__sep"></span>

      <!-- Control Status Badge: VIEW ONLY vs CONTROL ACTIVE -->
      <div class="toolbar__mode-container">
        <span
          v-if="isControlling"
          class="badge-mode badge-mode--active"
          title="Interactive mouse and keyboard control active"
        >
          <span class="pulse-beacon"></span>
          <strong>CONTROL ACTIVE</strong>
        </span>
        <span
          v-else
          class="badge-mode badge-mode--view"
          title="Remote screen is in View Only mode. Click Take Control to interact."
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
          <strong>VIEW ONLY</strong>
        </span>
      </div>

      <!-- Mouse & Keyboard input status -->
      <span
        class="input-badge"
        :class="isControlling ? 'input-badge--active' : 'input-badge--disabled'"
        :title="isControlling ? 'Mouse and keyboard inputs transmitted to remote computer' : 'Mouse and keyboard inputs disabled in View Only mode'"
      >
        <svg v-if="isControlling" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="2" y="4" width="20" height="16" rx="2"/>
          <line x1="6" y1="8" x2="6" y2="8"/>
          <line x1="10" y1="8" x2="10" y2="8"/>
          <line x1="14" y1="8" x2="14" y2="8"/>
          <line x1="18" y1="8" x2="18" y2="8"/>
          <line x1="6" y1="12" x2="6" y2="12"/>
          <line x1="18" y1="12" x2="18" y2="12"/>
          <line x1="8" y1="16" x2="16" y2="16"/>
        </svg>
        <svg v-else width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
        <span>{{ isControlling ? 'Input Active' : 'Input Disabled' }}</span>
      </span>
    </div>

    <!-- Prominent Center: Take Control / Release Control Button -->
    <div class="toolbar__center">
      <button
        v-if="!isControlling"
        id="btn-take-control"
        class="btn-control-action btn-control-action--take"
        :disabled="connectionState !== 'connected' || controlPending"
        @click="$emit('take-control')"
        :title="controlPending ? 'Establishing remote control connection...' : 'Take Control: Enable interactive mouse & keyboard control on remote computer'"
      >
        <span v-if="controlPending" class="toolbar-spinner"></span>
        <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
          <polygon points="5 3 19 12 5 21 5 3" fill="currentColor"/>
        </svg>
        <span>{{ controlPending ? 'Connecting...' : 'Take Control' }}</span>
      </button>

      <button
        v-else
        id="btn-release-control"
        class="btn-control-action btn-control-action--release"
        @click="$emit('release-control')"
        title="Release Control: Stop sending mouse & keyboard input, revert to View Only mode"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
          <rect x="5" y="5" width="14" height="14" rx="2" fill="currentColor"/>
        </svg>
        <span>Release Control</span>
      </button>
    </div>

    <div class="toolbar__right">
      <!-- Clipboard Sync -->
      <button
        id="btn-clipboard-sync"
        class="btn btn--ghost btn--icon"
        @click="$emit('clipboard-sync')"
        title="Clipboard: Sync local clipboard to remote computer"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
          <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
        </svg>
      </button>

      <!-- File Transfer -->
      <button
        id="btn-file-transfer"
        class="btn btn--ghost btn--icon"
        @click="$emit('toggle-files')"
        title="File Transfer: Browse and transfer files with remote host"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>
          <polyline points="13 2 13 9 20 9"/>
        </svg>
      </button>

      <!-- Chat -->
      <button
        id="btn-chat"
        class="btn btn--ghost btn--icon chat-toggle"
        @click="$emit('toggle-chat')"
        title="In-Session Chat"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        </svg>
        <span v-if="unreadCount > 0" class="chat-badge">{{ unreadCount }}</span>
      </button>

      <!-- Terminal / SSH -->
      <button
        id="btn-terminal"
        class="btn btn--ghost btn--icon"
        @click="$emit('toggle-terminal')"
        title="Interactive Terminal / SSH on remote host"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="4 17 10 11 4 5"/>
          <line x1="12" y1="19" x2="20" y2="19"/>
        </svg>
      </button>

      <!-- Screen / Multi-Monitor Selector -->
      <MonitorSelector
        :monitors="monitors"
        :current-monitor="currentMonitor"
        @switch="$emit('switch-monitor', $event)"
      />

      <!-- Connection Stats Toggle -->
      <button
        id="btn-stats"
        class="btn btn--ghost btn--icon"
        @click="$emit('toggle-stats')"
        title="Connection Quality & Network Stats"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
        </svg>
      </button>

      <!-- Settings -->
      <button
        id="btn-settings"
        class="btn btn--ghost btn--icon"
        @click="$emit('open-settings')"
        title="Session & Network Settings"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </button>

      <span class="toolbar__sep"></span>

      <!-- Fullscreen -->
      <button
        id="btn-fullscreen"
        class="btn btn--ghost btn--icon"
        @click="$emit('fullscreen')"
        title="Toggle Fullscreen"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M8 3H5a2 2 0 0 0-2 2v3"/>
          <path d="M21 8V5a2 2 0 0 0-2-2h-3"/>
          <path d="M3 16v3a2 2 0 0 0 2 2h3"/>
          <path d="M16 21h3a2 2 0 0 0 2-2v-3"/>
        </svg>
      </button>

      <!-- Disconnect -->
      <button
        id="btn-disconnect"
        class="btn btn--danger"
        @click="$emit('disconnect')"
        title="Disconnect Session"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
        Disconnect
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import MonitorSelector from './MonitorSelector.vue'

const props = defineProps({
  connectionState: { type: String, default: 'new' },
  dataChannelState: { type: String, default: 'closed' },
  sessionCode: { type: String, default: '' },
  hostInfo: { type: Object, default: null },
  monitors: { type: Array, default: () => [] },
  currentMonitor: { type: Number, default: 1 },
  unreadCount: { type: Number, default: 0 },
  isControlling: { type: Boolean, default: false },
  controlPending: { type: Boolean, default: false },
})

defineEmits([
  'disconnect',
  'fullscreen',
  'toggle-stats',
  'toggle-chat',
  'toggle-files',
  'toggle-terminal',
  'clipboard-sync',
  'switch-monitor',
  'open-settings',
  'take-control',
  'release-control',
])

const statusDotClass = computed(() => {
  const m = { connected: 'status-dot--connected', failed: 'status-dot--offline', disconnected: 'status-dot--offline' }
  return m[props.connectionState] || 'status-dot--waiting'
})

const statusLabel = computed(() => {
  if (props.connectionState === 'connected') return 'Connected'
  return { connecting: 'Connecting...', failed: 'Failed', disconnected: 'Disconnected' }[props.connectionState] || 'Waiting...'
})
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 14px;
  background: #11141a;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  color: white;
  min-height: 48px;
  z-index: 20;
  position: relative;
  user-select: none;
}

.toolbar__left,
.toolbar__right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.toolbar__status {
  display: flex;
  align-items: center;
  gap: 6px;
}

.toolbar__screen-icon {
  color: rgba(255, 255, 255, 0.6);
}

.toolbar__status-text {
  font-size: 0.78rem;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
}

.toolbar__sep {
  width: 1px;
  height: 18px;
  background: rgba(255, 255, 255, 0.15);
  margin: 0 2px;
}

.toolbar__code {
  font-size: 0.78rem;
  font-weight: 600;
  color: #60a5fa;
  letter-spacing: 0.02em;
}

.toolbar__host {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.74rem;
  color: rgba(255, 255, 255, 0.6);
  padding-left: 2px;
}

/* Control Status Badges */
.toolbar__mode-container {
  display: flex;
  align-items: center;
}

.badge-mode {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 9999px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  transition: all 0.25s ease;
}

.badge-mode--view {
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.35);
  color: #93c5fd;
}

.badge-mode--active {
  background: rgba(16, 185, 129, 0.16);
  border: 1px solid rgba(16, 185, 129, 0.5);
  color: #34d399;
  box-shadow: 0 0 12px rgba(16, 185, 129, 0.25);
}

.pulse-beacon {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #34d399;
  box-shadow: 0 0 8px #34d399;
  animation: beacon-pulse 1.6s ease-in-out infinite;
}

@keyframes beacon-pulse {
  0% { transform: scale(0.9); opacity: 0.8; box-shadow: 0 0 4px #34d399; }
  50% { transform: scale(1.3); opacity: 1; box-shadow: 0 0 12px #34d399; }
  100% { transform: scale(0.9); opacity: 0.8; box-shadow: 0 0 4px #34d399; }
}

/* Mouse & Keyboard input badge */
.input-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 0.72rem;
  padding: 2px 7px;
  border-radius: 4px;
}

.input-badge--active {
  color: #6ee7b7;
  background: rgba(16, 185, 129, 0.1);
}

.input-badge--disabled {
  color: rgba(255, 255, 255, 0.4);
  background: rgba(255, 255, 255, 0.04);
}

/* Center Action Button */
.toolbar__center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-control-action {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 0.84rem;
  font-weight: 700;
  padding: 6px 20px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  outline: none;
}

.btn-control-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

/* Take Control - Emerald Radiant Gradient */
.btn-control-action--take {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.25);
  box-shadow: 0 2px 12px rgba(16, 185, 129, 0.45);
}

.btn-control-action--take:hover:not(:disabled) {
  background: linear-gradient(135deg, #34d399 0%, #10b981 100%);
  box-shadow: 0 4px 18px rgba(16, 185, 129, 0.65);
  transform: translateY(-1px);
}

.btn-control-action--take:active:not(:disabled) {
  transform: translateY(0);
}

/* Release Control - Amber/Crimson Warning Gradient */
.btn-control-action--release {
  background: linear-gradient(135deg, #f59e0b 0%, #dc2626 100%);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.25);
  box-shadow: 0 2px 14px rgba(220, 38, 38, 0.45);
  animation: active-glow 2.5s infinite;
}

.btn-control-action--release:hover {
  background: linear-gradient(135deg, #fbbf24 0%, #ef4444 100%);
  box-shadow: 0 4px 20px rgba(220, 38, 38, 0.65);
  transform: translateY(-1px);
}

.btn-control-action--release:active {
  transform: translateY(0);
}

@keyframes active-glow {
  0% { box-shadow: 0 0 10px rgba(245, 158, 11, 0.4); }
  50% { box-shadow: 0 0 18px rgba(220, 38, 38, 0.7); }
  100% { box-shadow: 0 0 10px rgba(245, 158, 11, 0.4); }
}

.toolbar-spinner {
  width: 13px;
  height: 13px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: tb-spin 0.7s linear infinite;
}

@keyframes tb-spin {
  to { transform: rotate(360deg); }
}

.chat-toggle {
  position: relative;
}

.chat-badge {
  position: absolute;
  top: -2px;
  right: -2px;
  font-size: 0.55rem;
  font-weight: 700;
  background: #f44336;
  color: white;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: 2px solid #11141a;
  animation: badge-pop 0.3s ease-out;
}

@keyframes badge-pop {
  from { transform: scale(0); }
  to { transform: scale(1); }
}

@media (max-width: 900px) {
  .input-badge,
  .toolbar__host {
    display: none;
  }
}
</style>
