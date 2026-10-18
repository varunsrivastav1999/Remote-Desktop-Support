<template>
  <div class="host">
    <div class="host__header">
      <button class="btn btn--ghost" @click="leave">Back</button>
      <h1>Share This Desk</h1>
      <button v-if="session.localStream.value" class="btn btn--danger" @click="stopSharing">Stop Sharing</button>
    </div>

    <div class="host__content">
      <section class="share-card">
        <p class="label">Your Remote Address</p>
        <p class="code font-mono">{{ formattedCode }}</p>
        <p class="status">
          <span :class="['status-dot', statusDot]"></span>
          {{ session.statusText.value }}
        </p>
        <button v-if="!session.localStream.value" class="btn btn--primary btn--lg" @click="beginShare">
          Select Screen to Share
        </button>
        <button v-if="session.sessionCode.value" class="btn btn--secondary" @click="copyCode">Copy Address</button>
        <p v-if="session.error.value" class="error">{{ session.error.value }}</p>
        <p class="privacy">
          Sharing begins only after you select a screen. Remote keyboard and mouse access begins only after you approve a controller request.
        </p>
      </section>

      <section class="preview">
        <video ref="videoEl" autoplay playsinline muted></video>
        <p v-if="!session.localStream.value" class="preview__empty">Your selected screen preview appears here.</p>
        <span v-else class="preview__badge">You are sharing</span>
      </section>
    </div>

    <div v-if="session.pendingController.value" class="approval-overlay">
      <div class="approval-card">
        <h2>Incoming control request</h2>
        <p>A user with your address wants to view and control the shared screen.</p>
        <div class="approval-actions">
          <button class="btn btn--secondary" @click="session.denyController()">Deny</button>
          <button class="btn btn--primary" @click="session.allowController()">{{ approvalButton }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { setHostedAddress } from '../composables/useMyAddress.js'
import { useHostSession } from '../composables/useHostSession.js'
import { isNativeApp } from '../composables/serverConfig.js'

const router = useRouter()
const videoEl = ref(null)
const session = useHostSession()
const nativeHost = isNativeApp()

const formattedCode = computed(() => session.sessionCode.value?.replace(/-/g, ' ') || 'Connecting...')
const approvalButton = computed(() => session.localStream.value ? 'Allow Control' : 'Allow and Choose Screen')
const statusDot = computed(() => {
  if (session.state.value === 'connected') return 'status-dot--connected'
  if (session.sessionCode.value) return 'status-dot--waiting'
  return 'status-dot--offline'
})

watch(() => session.localStream.value, (stream, previousStream) => {
  if (videoEl.value) videoEl.value.srcObject = stream
  if (!stream && previousStream && session.sessionCode.value) {
    session.stopSharing()
  }
})

watch(() => session.state.value, (state) => {
  if (session.sessionCode.value) setHostedAddress(session.sessionCode.value, state)
})

async function beginShare() {
  await session.start()
}

function copyCode() {
  navigator.clipboard?.writeText(session.sessionCode.value)
}

function stopSharing() {
  session.stopSharing()
}

function leave() {
  session.stopSharing()
  router.push('/')
}

onMounted(async () => {
  await session.ensureOnline()
  if (session.sessionCode.value) setHostedAddress(session.sessionCode.value, session.state.value)
})

onUnmounted(() => {
  session.stopSharing()
})
</script>

<style scoped>
.host { height:calc(100vh - 42px); background:var(--ad-bg); color:var(--ad-text); display:flex; flex-direction:column; }
.host__header { height:56px; padding:10px 20px; border-bottom:1px solid var(--ad-border); display:flex; gap:18px; align-items:center; }
.host__header h1 { font-size:1.05rem; flex:1; }
.host__content { flex:1; display:grid; grid-template-columns:340px 1fr; gap:24px; padding:28px; min-height:0; }
.share-card { background:var(--ad-surface); border:1px solid var(--ad-border); border-radius:12px; padding:26px; display:flex; flex-direction:column; align-items:flex-start; gap:18px; }
.label { font-size:0.75rem; text-transform:uppercase; letter-spacing:0.08em; color:var(--ad-text-muted); }
.code { font-size:1.8rem; font-weight:700; color:var(--color-accent-primary); letter-spacing:0.08em; }
.status { display:flex; gap:8px; align-items:center; color:var(--ad-text-muted); font-size:0.84rem; }
.privacy { margin-top:auto; border-top:1px solid var(--ad-border); padding-top:18px; color:var(--ad-text-muted); font-size:0.78rem; line-height:1.6; }
.error { font-size:0.8rem; color:#ef5350; line-height:1.5; }
.preview { border:1px solid var(--ad-border); border-radius:12px; background:#111; overflow:hidden; position:relative; display:flex; align-items:center; justify-content:center; }
.preview video { width:100%; height:100%; object-fit:contain; }
.preview__empty { color:rgba(255,255,255,0.45); font-size:0.9rem; }
.preview__badge { position:absolute; top:14px; left:14px; color:#fff; background:#d32f2f; padding:5px 10px; border-radius:20px; font-size:0.72rem; font-weight:600; }
.approval-overlay { position:fixed; inset:42px 0 0; background:rgba(0,0,0,0.6); display:flex; align-items:center; justify-content:center; z-index:80; }
.approval-card { width:410px; padding:30px; border-radius:12px; background:var(--ad-surface); border:1px solid var(--ad-border); box-shadow:0 12px 32px rgba(0,0,0,0.35); }
.approval-card h2 { font-size:1.1rem; margin-bottom:10px; }
.approval-card p { font-size:0.86rem; line-height:1.6; color:var(--ad-text-muted); margin-bottom:24px; }
.approval-actions { display:flex; justify-content:flex-end; gap:10px; }
</style>
