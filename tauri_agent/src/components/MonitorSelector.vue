<template>
  <div class="monitor-selector" v-if="monitors.length > 1">
    <button class="monitor-btn" @click="open = !open" title="Switch Monitor">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="2" y="3" width="20" height="14" rx="2"/>
        <line x1="8" y1="21" x2="16" y2="21"/>
        <line x1="12" y1="17" x2="12" y2="21"/>
      </svg>
      <span class="monitor-badge">{{ currentMonitor }}</span>
    </button>

    <transition name="dropdown">
      <div v-if="open" class="monitor-dropdown" @click.stop>
        <div class="monitor-dropdown__title">Monitors</div>
        <button
          v-for="mon in monitors"
          :key="mon.index"
          :class="['monitor-option', { 'monitor-option--active': mon.index === currentMonitor }]"
          @click="selectMonitor(mon.index)"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="2" y="3" width="20" height="14" rx="2"/>
            <line x1="8" y1="21" x2="16" y2="21"/>
            <line x1="12" y1="17" x2="12" y2="21"/>
          </svg>
          <div class="monitor-info">
            <span class="monitor-name">{{ mon.name }}</span>
            <span class="monitor-res">{{ mon.width }}×{{ mon.height }}</span>
          </div>
          <svg v-if="mon.index === currentMonitor" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4caf50" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
        </button>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  monitors: { type: Array, default: () => [] },
  currentMonitor: { type: Number, default: 1 },
})

const emit = defineEmits(['switch'])
const open = ref(false)

function selectMonitor(index) {
  emit('switch', index)
  open.value = false
}

function handleClickOutside(e) {
  if (open.value) open.value = false
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<style scoped>
.monitor-selector { position: relative; }

.monitor-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: rgba(255,255,255,0.7);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: 150ms;
  font-size: 0.78rem;
}
.monitor-btn:hover { color: white; background: rgba(255,255,255,0.1); }

.monitor-badge {
  font-size: 0.6rem;
  font-weight: 700;
  background: #d32f2f;
  color: white;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.monitor-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  background: rgba(30, 30, 30, 0.95);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 8px;
  min-width: 240px;
  padding: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  z-index: 50;
}

.monitor-dropdown__title {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(255,255,255,0.4);
  padding: 4px 8px 8px;
}

.monitor-option {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  background: none;
  border: none;
  border-radius: 6px;
  color: rgba(255,255,255,0.8);
  cursor: pointer;
  text-align: left;
  transition: 150ms;
}
.monitor-option:hover { background: rgba(255,255,255,0.08); }
.monitor-option--active { background: rgba(211,47,47,0.15); color: white; }

.monitor-info { display: flex; flex-direction: column; flex: 1; }
.monitor-name { font-size: 0.8rem; font-weight: 500; }
.monitor-res { font-size: 0.68rem; color: rgba(255,255,255,0.4); }

.dropdown-enter-active { animation: slide-down 0.15s ease-out; }
.dropdown-leave-active { animation: slide-down 0.1s ease-in reverse; }
@keyframes slide-down { from { opacity:0; transform:translateY(-4px); } to { opacity:1; transform:translateY(0); } }
</style>
