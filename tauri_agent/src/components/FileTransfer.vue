<template>
  <transition name="filepanel-slide">
    <div v-if="visible" class="file-panel">
      <div class="file-header">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/></svg>
        <span>File Transfer</span>
        <button class="file-close" @click="$emit('close')">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      <!-- Path Breadcrumb -->
      <div class="file-breadcrumb">
        <button class="bread-btn" @click="ft.navigateUp()" title="Go Up">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
        </button>
        <span class="bread-path font-mono">{{ ft.remotePath.value }}</span>
        <button class="bread-btn" @click="ft.listDirectory(ft.remotePath.value)" title="Refresh">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        </button>
      </div>

      <!-- Transfer Progress -->
      <div v-if="ft.activeTransfer.name" class="transfer-bar">
        <div class="transfer-info">
          <span class="transfer-name">{{ ft.activeTransfer.direction === 'upload' ? '↑' : '↓' }} {{ ft.activeTransfer.name }}</span>
          <span class="transfer-speed">{{ ft.activeTransfer.speed }}</span>
        </div>
        <div class="transfer-progress">
          <div class="transfer-progress__fill" :style="{ width: ft.activeTransfer.progress + '%' }"></div>
        </div>
        <span class="transfer-pct">{{ ft.activeTransfer.progress }}%</span>
      </div>

      <!-- File List -->
      <div class="file-list"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="handleDrop"
        :class="{ 'file-list--drag': dragOver }"
      >
        <div v-if="ft.isLoading.value" class="file-loading">
          <span class="file-spinner"></span>
          Loading...
        </div>

        <div v-else-if="ft.remoteEntries.value.length === 0" class="file-empty">
          <p>Empty directory</p>
        </div>

        <template v-else>
          <div
            v-for="entry in ft.remoteEntries.value"
            :key="entry.path"
            :class="['file-item', { 'file-item--dir': entry.is_dir }]"
            @dblclick="entry.is_dir ? ft.listDirectory(entry.path) : ft.downloadFile(entry.path)"
          >
            <!-- Icon -->
            <div class="file-icon">
              <svg v-if="entry.is_dir" width="16" height="16" viewBox="0 0 24 24" fill="#ffd54f" stroke="#ffd54f" stroke-width="1">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.5)" stroke-width="1.5">
                <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><polyline points="13 2 13 9 20 9"/>
              </svg>
            </div>

            <!-- Info -->
            <div class="file-info">
              <span class="file-name">{{ entry.name }}</span>
              <span v-if="!entry.is_dir" class="file-size">{{ formatSize(entry.size) }}</span>
            </div>

            <!-- Actions -->
            <div class="file-actions">
              <button v-if="!entry.is_dir" class="file-act-btn" @click.stop="ft.downloadFile(entry.path)" title="Download">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              </button>
              <button class="file-act-btn file-act-btn--danger" @click.stop="ft.deleteItem(entry.path)" title="Delete">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </div>
        </template>
      </div>

      <!-- Upload Button -->
      <div class="file-footer">
        <input type="file" ref="fileInput" @change="handleFileSelect" style="display:none" multiple />
        <button class="upload-btn" @click="$refs.fileInput.click()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          Upload Files
        </button>
        <span class="file-hint">or drag & drop files here</span>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useFileTransfer } from '../composables/useFileTransfer.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  fileChannel: { type: Object, default: null },
})

defineEmits(['close'])

const ft = useFileTransfer(ref(null))
const dragOver = ref(false)
const fileInput = ref(null)

// Setup channel when it becomes available
watch(() => props.fileChannel, (dc) => {
  if (dc && dc.readyState === 'open') {
    ft.setupChannel(dc)
  } else if (dc) {
    dc.onopen = () => ft.setupChannel(dc)
  }
}, { immediate: true })

function handleFileSelect(event) {
  const files = event.target.files
  for (const file of files) {
    ft.uploadFile(file)
  }
  event.target.value = '' // Reset input
}

function handleDrop(event) {
  dragOver.value = false
  const files = event.dataTransfer?.files
  if (files) {
    for (const file of files) {
      ft.uploadFile(file)
    }
  }
}

function formatSize(bytes) {
  if (bytes === 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}
</script>

<style scoped>
.file-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: 380px;
  height: 100%;
  background: rgba(20, 20, 20, 0.95);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-left: 1px solid rgba(255,255,255,0.08);
  display: flex;
  flex-direction: column;
  z-index: 40;
  box-shadow: -4px 0 24px rgba(0,0,0,0.3);
  color: #e0e0e0;
}

.file-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  font-weight: 600;
  font-size: 0.85rem;
  color: white;
  flex-shrink: 0;
}

.file-close {
  margin-left: auto;
  background: none;
  border: none;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  padding: 4px;
  display: flex;
  border-radius: 4px;
  transition: 150ms;
}
.file-close:hover { color: white; background: rgba(255,255,255,0.1); }

.file-breadcrumb {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  flex-shrink: 0;
}

.bread-btn {
  background: none;
  border: none;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  padding: 4px;
  display: flex;
  border-radius: 4px;
  transition: 150ms;
}
.bread-btn:hover { color: white; background: rgba(255,255,255,0.1); }

.bread-path {
  flex: 1;
  font-size: 0.7rem;
  color: rgba(255,255,255,0.6);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Transfer Progress */
.transfer-bar {
  padding: 8px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  flex-shrink: 0;
}
.transfer-info { display: flex; justify-content: space-between; margin-bottom: 4px; }
.transfer-name { font-size: 0.72rem; color: rgba(255,255,255,0.7); }
.transfer-speed { font-size: 0.68rem; color: #4caf50; font-family: monospace; }
.transfer-progress { height: 3px; background: rgba(255,255,255,0.1); border-radius: 2px; overflow: hidden; }
.transfer-progress__fill { height: 100%; background: linear-gradient(90deg, #d32f2f, #ff5252); border-radius: 2px; transition: width 200ms; }
.transfer-pct { font-size: 0.65rem; color: rgba(255,255,255,0.4); display: block; text-align: right; margin-top: 2px; }

/* File List */
.file-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  transition: background 200ms;
}
.file-list--drag { background: rgba(211,47,47,0.08); }

.file-loading, .file-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 8px;
  color: rgba(255,255,255,0.3);
  font-size: 0.82rem;
}

.file-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255,255,255,0.1);
  border-top-color: #d32f2f;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 100ms;
}
.file-item:hover { background: rgba(255,255,255,0.06); }
.file-item--dir { cursor: pointer; }

.file-icon { width: 20px; display: flex; flex-shrink: 0; }

.file-info { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.file-name { font-size: 0.78rem; color: #e0e0e0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.file-item--dir .file-name { color: #ffd54f; font-weight: 500; }
.file-size { font-size: 0.65rem; color: rgba(255,255,255,0.35); font-family: monospace; }

.file-actions { display: flex; gap: 4px; opacity: 0; transition: opacity 100ms; }
.file-item:hover .file-actions { opacity: 1; }

.file-act-btn {
  background: none;
  border: none;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  padding: 4px;
  display: flex;
  border-radius: 4px;
  transition: 150ms;
}
.file-act-btn:hover { color: white; background: rgba(255,255,255,0.1); }
.file-act-btn--danger:hover { color: #f44336; background: rgba(244,67,54,0.1); }

/* Footer */
.file-footer {
  padding: 12px 16px;
  border-top: 1px solid rgba(255,255,255,0.08);
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.upload-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 0.78rem;
  font-weight: 600;
  background: #d32f2f;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: 150ms;
}
.upload-btn:hover { background: #b71c1c; }

.file-hint { font-size: 0.68rem; color: rgba(255,255,255,0.3); }

@keyframes spin { to { transform: rotate(360deg); } }

.filepanel-slide-enter-active { animation: slide-right 0.25s ease-out; }
.filepanel-slide-leave-active { animation: slide-right 0.2s ease-in reverse; }
@keyframes slide-right { from { opacity:0; transform:translateX(20px); } to { opacity:1; transform:translateX(0); } }
</style>
