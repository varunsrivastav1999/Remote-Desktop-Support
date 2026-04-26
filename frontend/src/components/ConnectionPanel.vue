<template>
  <div class="conn-panel">
    <div class="conn-card card">
      <div class="conn-card__spinner-ring">
        <div class="conn-card__dot">
          <span class="status-dot" :class="statusDotClass"></span>
        </div>
      </div>
      <h2 class="conn-card__title">{{ title }}</h2>
      <p class="conn-card__sub text-secondary">{{ subtitle }}</p>
      <div v-if="sessionCode" class="conn-card__code">
        <span class="text-muted" style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em">Session</span>
        <span class="session-code" style="font-size:1.6rem">{{ sessionCode }}</span>
      </div>
      <div class="conn-steps">
        <div v-for="(step,i) in steps" :key="i" :class="['cstep',{'cstep--done':step.done,'cstep--active':step.active}]">
          <div class="cstep__ind">
            <svg v-if="step.done" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
            <span v-else-if="step.active" class="cstep__spin"></span>
            <span v-else class="cstep__dot"></span>
          </div>
          <span class="cstep__label">{{ step.label }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  state:{type:String,default:'new'}, iceState:{type:String,default:'new'},
  sessionCode:{type:String,default:''}, signalingConnected:{type:Boolean,default:false},
})
const statusDotClass = computed(() => ({connected:'status-dot--connected',failed:'status-dot--offline',disconnected:'status-dot--offline'}[props.state]||'status-dot--waiting'))
const title = computed(() => ({connected:'Connected!',connecting:'Establishing Connection...',failed:'Connection Failed',disconnected:'Disconnected'}[props.state]||'Connecting to Host...'))
const subtitle = computed(() => ({connected:'Remote screen is now visible.',connecting:'Negotiating peer-to-peer connection...',failed:'Could not connect. Check network.',disconnected:'The remote host disconnected.'}[props.state]||'Waiting for host agent...'))
const steps = computed(() => [
  {label:'Signaling server',done:props.signalingConnected,active:!props.signalingConnected},
  {label:'Peer discovered',done:['connecting','connected'].includes(props.state),active:props.signalingConnected&&props.state==='new'},
  {label:'ICE negotiation',done:props.iceState==='connected'||props.iceState==='completed',active:props.iceState==='checking'},
  {label:'Stream established',done:props.state==='connected',active:props.state==='connecting'},
])
</script>

<style scoped>
.conn-panel { width:100%; height:100%; display:flex; align-items:center; justify-content:center; padding:var(--space-xl); background:var(--color-bg-primary); }
.conn-card { display:flex; flex-direction:column; align-items:center; padding:var(--space-2xl) var(--space-xl); max-width:380px; width:100%; text-align:center; }
.conn-card__spinner-ring { position:relative; width:64px; height:64px; margin-bottom:var(--space-lg); }
.conn-card__spinner-ring::before { content:''; position:absolute; inset:0; border:2px solid transparent; border-top-color:var(--color-accent-primary); border-right-color:var(--color-accent-primary); border-radius:50%; animation:spin 2s linear infinite; }
.conn-card__dot { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; }
.conn-card__dot .status-dot { width:14px; height:14px; }
.conn-card__title { font-size:1.1rem; font-weight:700; margin-bottom:4px; }
.conn-card__sub { font-size:0.85rem; margin-bottom:var(--space-lg); }
.conn-card__code { display:flex; flex-direction:column; gap:2px; margin-bottom:var(--space-lg); }
.conn-steps { display:flex; flex-direction:column; gap:var(--space-sm); width:100%; text-align:left; }
.cstep { display:flex; align-items:center; gap:var(--space-sm); padding:6px var(--space-md); border-radius:var(--border-radius-sm); }
.cstep--active { background:var(--color-accent-orange-light); }
.cstep--done { background:var(--color-accent-green-light); }
.cstep__ind { width:20px; height:20px; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.cstep--done .cstep__ind { color:var(--color-accent-green); }
.cstep__dot { width:6px; height:6px; border-radius:50%; background:var(--color-text-muted); opacity:0.4; }
.cstep__spin { width:14px; height:14px; border:2px solid rgba(245,124,0,0.3); border-top-color:var(--color-accent-orange); border-radius:50%; animation:spin 0.8s linear infinite; }
.cstep__label { font-size:0.82rem; color:var(--color-text-secondary); }
.cstep--done .cstep__label { color:var(--color-text-primary); }
.cstep--active .cstep__label { color:var(--color-accent-orange); font-weight:500; }
</style>
