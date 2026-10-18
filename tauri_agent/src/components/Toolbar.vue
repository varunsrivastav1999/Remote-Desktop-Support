<template>
  <div class="toolbar">
    <div class="toolbar__left">
      <span class="toolbar__status">
        <span class="status-dot" :class="statusDotClass"></span>
        <span class="toolbar__status-text">{{ statusLabel }}</span>
      </span>
      <span class="toolbar__sep"></span>
      <span class="toolbar__code font-mono">{{ sessionCode }}</span>
      <span v-if="hostInfo" class="toolbar__host">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        {{ hostInfo.hostname }}
      </span>
    </div>
    <div class="toolbar__center">Remote Desktop Session</div>
    <div class="toolbar__right">
      <!-- Monitor Selector -->
      <MonitorSelector
        :monitors="monitors"
        :current-monitor="currentMonitor"
        @switch="$emit('switch-monitor', $event)"
      />

      <!-- Terminal / SSH -->
      <button class="btn btn--ghost btn--icon" @click="$emit('toggle-terminal')" title="Interactive Terminal">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
      </button>

      <!-- File Transfer -->
      <button class="btn btn--ghost btn--icon" @click="$emit('toggle-files')" title="File Transfer">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
      </button>

      <!-- Chat -->
      <button class="btn btn--ghost btn--icon chat-toggle" @click="$emit('toggle-chat')" title="In-Session Chat">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span v-if="unreadCount > 0" class="chat-badge">{{ unreadCount }}</span>
      </button>

      <!-- Stats Toggle -->
      <button class="btn btn--ghost btn--icon" @click="$emit('toggle-stats')" title="Connection Stats">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
      </button>

      <span class="toolbar__sep"></span>

      <!-- Fullscreen -->
      <button id="btn-fullscreen" class="btn btn--ghost btn--icon" @click="$emit('fullscreen')" title="Fullscreen">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></svg>
      </button>

      <!-- Disconnect -->
      <button id="btn-disconnect" class="btn btn--danger" @click="$emit('disconnect')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
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
})

defineEmits([
  'disconnect', 'fullscreen', 'toggle-stats', 'toggle-chat',
  'toggle-files', 'toggle-terminal', 'clipboard-sync', 'switch-monitor',
])

const statusDotClass = computed(() => {
  const m = { connected:'status-dot--connected', failed:'status-dot--offline', disconnected:'status-dot--offline' }
  return m[props.connectionState] || 'status-dot--waiting'
})
const statusLabel = computed(() => {
  if (props.connectionState==='connected' && props.dataChannelState==='open') return 'Connected (Control Active)'
  if (props.connectionState==='connected') return 'Connected (View Only)'
  return { connecting:'Connecting...', failed:'Failed', disconnected:'Disconnected' }[props.connectionState] || 'Waiting...'
})
</script>

<style scoped>
.toolbar { display:flex; align-items:center; justify-content:space-between; padding:var(--space-sm) var(--space-md); background:var(--color-bg-header); color:white; min-height:44px; z-index:10; }
.toolbar__left,.toolbar__right { display:flex; align-items:center; gap:var(--space-sm); }
.toolbar__center { position:absolute; left:50%; transform:translateX(-50%); font-size:0.78rem; font-weight:500; color:rgba(255,255,255,0.5); text-transform:uppercase; letter-spacing:0.06em; }
.toolbar__status { display:flex; align-items:center; gap:6px; }
.toolbar__status-text { font-size:0.78rem; color:rgba(255,255,255,0.8); }
.toolbar__sep { width:1px; height:18px; background:rgba(255,255,255,0.15); }
.toolbar__code { font-size:0.78rem; color:rgba(255,255,255,0.5); }
.toolbar__host { display:flex; align-items:center; gap:4px; font-size:0.72rem; color:rgba(255,255,255,0.4); padding-left:6px; }

.chat-toggle { position:relative; }
.chat-badge {
  position:absolute; top:-2px; right:-2px;
  font-size:0.55rem; font-weight:700;
  background:#f44336; color:white;
  width:16px; height:16px;
  display:flex; align-items:center; justify-content:center;
  border-radius:50%;
  border:2px solid var(--color-bg-header);
  animation: badge-pop 0.3s ease-out;
}
@keyframes badge-pop { from { transform:scale(0); } to { transform:scale(1); } }
</style>
