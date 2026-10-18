<template>
  <transition name="stats-slide">
    <div v-if="visible" class="stats-overlay">
      <div class="stats-header">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
        <span>Connection Stats</span>
        <button class="stats-close" @click="$emit('close')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div class="stats-grid">
        <div class="stat-item">
          <span class="stat-label">Latency</span>
          <span :class="['stat-value', latencyClass]">{{ stats.latency }} ms</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">FPS</span>
          <span class="stat-value">{{ stats.fps }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Bitrate</span>
          <span class="stat-value">{{ stats.bitrateFormatted }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Resolution</span>
          <span class="stat-value">{{ stats.resolution || '—' }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Codec</span>
          <span class="stat-value">{{ stats.codec || '—' }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Connection</span>
          <span :class="['stat-value', connectionClass]">{{ stats.connectionType || '—' }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Packets Lost</span>
          <span class="stat-value">{{ stats.packetsLost }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Jitter</span>
          <span class="stat-value">{{ (stats.jitter * 1000).toFixed(1) }} ms</span>
        </div>
      </div>
      <div class="stats-quality">
        <span class="stat-label">Quality</span>
        <select :value="currentQuality" @change="$emit('quality-change', $event.target.value)" class="quality-sel">
          <option value="ultra-low">Ultra Low (10kbps)</option>
          <option value="low">Low Bandwidth</option>
          <option value="medium">Balanced</option>
          <option value="high">High Quality</option>
          <option value="ultra">Ultra (LAN)</option>
        </select>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  stats: { type: Object, required: true },
  currentQuality: { type: String, default: 'medium' },
})

defineEmits(['close', 'quality-change'])

const latencyClass = computed(() => {
  if (props.stats.latency < 50) return 'stat--good'
  if (props.stats.latency < 150) return 'stat--warn'
  return 'stat--bad'
})

const connectionClass = computed(() => {
  if (props.stats.candidateType === 'host') return 'stat--good'
  if (props.stats.candidateType === 'srflx') return 'stat--warn'
  return 'stat--bad'
})
</script>

<style scoped>
.stats-overlay {
  position: absolute;
  top: 52px;
  right: 12px;
  width: 260px;
  background: rgba(20, 20, 20, 0.92);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 10px;
  padding: 14px;
  z-index: 50;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  color: #e0e0e0;
  font-size: 0.78rem;
}

.stats-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
  font-size: 0.82rem;
  color: white;
}

.stats-close {
  margin-left: auto;
  background: none;
  border: none;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  padding: 2px;
  display: flex;
  border-radius: 4px;
  transition: all 150ms;
}
.stats-close:hover { color: white; background: rgba(255,255,255,0.1); }

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 8px;
  background: rgba(255,255,255,0.04);
  border-radius: 6px;
}

.stat-label {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(255,255,255,0.4);
}

.stat-value {
  font-size: 0.85rem;
  font-weight: 600;
  font-family: 'Fira Code', 'SF Mono', monospace;
}

.stat--good { color: #4caf50; }
.stat--warn { color: #ff9800; }
.stat--bad { color: #f44336; }

.stats-quality {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid rgba(255,255,255,0.08);
}

.quality-sel {
  padding: 4px 8px;
  font-size: 0.75rem;
  background: rgba(255,255,255,0.08);
  color: white;
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 4px;
  outline: none;
  cursor: pointer;
}
.quality-sel option { background: #222; }

.stats-slide-enter-active { animation: slide-down 0.2s ease-out; }
.stats-slide-leave-active { animation: slide-down 0.15s ease-in reverse; }
@keyframes slide-down { from { opacity:0; transform:translateY(-8px); } to { opacity:1; transform:translateY(0); } }
</style>
