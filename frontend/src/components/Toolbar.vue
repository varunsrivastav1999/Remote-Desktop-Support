<template>
  <div class="toolbar">
    <div class="toolbar__left">
      <span class="toolbar__status">
        <span class="status-dot" :class="statusDotClass"></span>
        <span class="toolbar__status-text">{{ statusLabel }}</span>
      </span>
      <span class="toolbar__sep"></span>
      <span class="toolbar__code font-mono">{{ sessionCode }}</span>
    </div>
    <div class="toolbar__center">Remote Session</div>
    <div class="toolbar__right">
      <button id="btn-fullscreen" class="btn btn--ghost btn--icon" @click="$emit('fullscreen')" title="Fullscreen">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></svg>
      </button>
      <button id="btn-disconnect" class="btn btn--danger" @click="$emit('disconnect')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        Disconnect
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  connectionState: { type: String, default: 'new' },
  dataChannelState: { type: String, default: 'closed' },
  sessionCode: { type: String, default: '' },
})
defineEmits(['disconnect', 'fullscreen'])

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
</style>
