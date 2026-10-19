import { ref, readonly, onMounted, onUnmounted } from 'vue'
import { apiUrl, loadNetworkSettings, isNativeApp } from './serverConfig.js'

const DEVICE_ID_KEY = 'remote_support_device_id'
const DEVICE_TOKEN_KEY = 'remote_support_device_token'
const DEVICE_NAME_KEY = 'remote_support_device_name'
const LEGACY_ID_KEY = 'anygravity_device_id'
const LEGACY_TOKEN_KEY = 'anygravity_device_token'
const LEGACY_NAME_KEY = 'anygravity_device_name'

const deviceId = ref('')
const deviceToken = ref('')
const deviceName = ref('')
const deviceStatus = ref('offline') // 'offline' | 'connecting' | 'online' | 'connected'
const incomingRequest = ref(null) // { requestId, callerDeviceId, callerName }

let heartbeatTimer = null
let deviceWs = null
let wsReconnectTimer = null
let wsReconnectAttempts = 0

function getTabSessionId() {
  if (typeof window === 'undefined') return 'server'
  if (!window.name || !window.name.startsWith('rs_tab_')) {
    window.name = `rs_tab_${Math.random().toString(36).slice(2, 10)}`
  }
  return window.name
}

function getDeviceStorage() {
  // In native desktop app (Tauri), persist permanently in localStorage.
  // In web browsers (Chrome, Firefox, Edge), use sessionStorage scoped per tab.
  if (isNativeApp()) {
    return localStorage
  }
  return sessionStorage
}

function hostPlatform() {
  const p = (navigator.userAgentData?.platform || navigator.platform || '').toLowerCase()
  if (p.includes('mac')) return 'macos'
  if (p.includes('win')) return 'windows'
  if (p.includes('linux')) return 'linux'
  return 'desktop'
}

function hostLabel() {
  const storage = getDeviceStorage()
  const custom = storage.getItem(DEVICE_NAME_KEY) || storage.getItem(LEGACY_NAME_KEY)
  if (custom) return custom
  const platform = hostPlatform().toUpperCase()
  return `${platform} Device`
}

function loadSavedCredentials() {
  const storage = getDeviceStorage()

  // In browser, ensure newly duplicated tabs get a fresh Device ID
  if (!isNativeApp() && typeof window !== 'undefined') {
    const currentTab = getTabSessionId()
    const storedTab = storage.getItem('rs_tab_owner')
    if (storedTab && storedTab !== currentTab) {
      // Tab was duplicated or session cloned: start fresh
      storage.removeItem(DEVICE_ID_KEY)
      storage.removeItem(DEVICE_TOKEN_KEY)
      deviceId.value = ''
      deviceToken.value = ''
    }
    storage.setItem('rs_tab_owner', currentTab)
  }

  const savedId = (storage.getItem(DEVICE_ID_KEY) || storage.getItem(LEGACY_ID_KEY) || '').trim()
  // Only accept valid permanent AG-XXX-XXX-XXX format.
  // If a stale legacy UUID is stored, discard it so backend allocates a proper AG ID.
  if (/^AG-\d{3}-\d{3}-\d{3}$/.test(savedId)) {
    deviceId.value = savedId
    deviceToken.value = storage.getItem(DEVICE_TOKEN_KEY) || storage.getItem(LEGACY_TOKEN_KEY) || ''
  } else {
    deviceId.value = ''
    deviceToken.value = ''
    storage.removeItem(DEVICE_ID_KEY)
    storage.removeItem(LEGACY_ID_KEY)
    storage.removeItem(DEVICE_TOKEN_KEY)
    storage.removeItem(LEGACY_TOKEN_KEY)
  }
  deviceName.value = storage.getItem(DEVICE_NAME_KEY) || storage.getItem(LEGACY_NAME_KEY) || hostLabel()
}

function saveCredentials(id, token, name) {
  const storage = getDeviceStorage()
  deviceId.value = id
  deviceToken.value = token
  if (name) deviceName.value = name
  storage.setItem(DEVICE_ID_KEY, id)
  storage.setItem(DEVICE_TOKEN_KEY, token)
  if (name) storage.setItem(DEVICE_NAME_KEY, name)
}

/**
 * Register or recover permanent Device ID with backend
 */
async function registerDevice() {
  loadSavedCredentials()
  deviceStatus.value = 'connecting'
  const settings = loadNetworkSettings()

  const payload = JSON.stringify({
    device_id: deviceId.value || null,
    auth_token: deviceToken.value || null,
    name: deviceName.value || hostLabel(),
    platform: hostPlatform(),
    agent_version: 'Remote Desktop Agent 1.0',
    unattended_enabled: settings.unattendedEnabled || false,
    pin: settings.unattendedPin || null,
  })

  const endpoints = [
    apiUrl('/api/v1/devices/register', settings),
    '/api/v1/devices/register',
    'http://localhost:8000/api/v1/devices/register',
  ]

  let lastError = null
  for (const endpoint of endpoints) {
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
      })

      if (response.ok) {
        const data = await response.json()
        saveCredentials(data.device_id, data.auth_token, data.name)
        deviceStatus.value = 'online'
        console.log(`[Remote Desktop] Registered as ${data.device_id} (${data.name})`)

        startHeartbeat()
        connectDevicePushWs()
        return true
      }

      if (response.status === 400 || response.status === 422) {
        // Clear stale credentials from storage and memory
        const storage = getDeviceStorage()
        storage.removeItem(DEVICE_ID_KEY)
        storage.removeItem(LEGACY_ID_KEY)
        storage.removeItem(DEVICE_TOKEN_KEY)
        storage.removeItem(LEGACY_TOKEN_KEY)
        deviceId.value = ''
        deviceToken.value = ''

        // Retry immediately requesting a fresh permanent Device ID
        const retryRes = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            device_id: null,
            auth_token: null,
            name: hostLabel(),
            platform: hostPlatform(),
            agent_version: 'Remote Desktop Agent 1.0',
            unattended_enabled: settings.unattendedEnabled || false,
            pin: settings.unattendedPin || null,
          }),
        })
        if (retryRes.ok) {
          const freshData = await retryRes.json()
          saveCredentials(freshData.device_id, freshData.auth_token, freshData.name)
          deviceStatus.value = 'online'
          startHeartbeat()
          connectDevicePushWs()
          return true
        }
      }
    } catch (err) {
      lastError = err
    }
  }

  console.error('[Remote Desktop] Failed to register device across all endpoints:', lastError)
  deviceStatus.value = 'offline'
  return false
}

/**
 * Heartbeat sender (every 15 seconds)
 */
function startHeartbeat() {
  stopHeartbeat()
  heartbeatTimer = setInterval(async () => {
    if (!deviceId.value) return
    const settings = loadNetworkSettings()
    try {
      const res = await fetch(apiUrl('/api/v1/devices/heartbeat', settings), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          device_id: deviceId.value,
          auth_token: deviceToken.value || '',
          platform: hostPlatform(),
        }),
      })

      if (res.status === 401 || res.status === 404) {
        console.warn('[Remote Support] Heartbeat credentials rejected by server, re-registering...')
        await registerDevice()
        return
      }

      if (res.ok) {
        const data = await res.json()
        if (deviceStatus.value === 'offline' || deviceStatus.value === 'connecting') {
          deviceStatus.value = 'online'
        }
        if (data.pending_request) {
          console.log('[Remote Desktop] Heartbeat delivered pending request:', data.pending_request)
          handlePushMessage(data.pending_request)
        }
      }

      // Ensure device push WebSocket is connected
      if (!deviceWs || deviceWs.readyState === WebSocket.CLOSED) {
        connectDevicePushWs()
      }
    } catch (e) {
      console.warn('[Remote Support] Heartbeat failed:', e)
    }
  }, 15000)
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
}

let deviceWsPingInterval = null

/**
 * WebSocket for real-time incoming connection requests: /ws/device/{device_id}
 */
function connectDevicePushWs() {
  if (!deviceId.value) return
  if (deviceWs && (deviceWs.readyState === WebSocket.OPEN || deviceWs.readyState === WebSocket.CONNECTING)) {
    return
  }
  if (deviceWs) {
    try { deviceWs.close(1000) } catch (_) {}
    deviceWs = null
  }

  const settings = loadNetworkSettings()
  let url
  try {
    const signalingServer = (settings.signalingServer || '').trim()
    if (signalingServer) {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const base = signalingServer.replace(/^https?:\/\//, '').replace(/^wss?:\/\//, '').replace(/\/ws\/?$/, '')
      url = `${proto}://${base}/ws/device/${deviceId.value}`
    } else {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      url = `${proto}://${window.location.host}/ws/device/${deviceId.value}`
    }
  } catch (e) {
    console.error('[Remote Desktop] Failed to construct device WS url:', e)
    return
  }

  try {
    deviceWs = new WebSocket(url)
  } catch (e) {
    scheduleWsReconnect()
    return
  }

  deviceWs.onopen = () => {
    console.log(`[Remote Desktop] Connected to device push channel: ${deviceId.value}`)
    wsReconnectAttempts = 0
    clearInterval(deviceWsPingInterval)
    deviceWsPingInterval = setInterval(() => {
      if (deviceWs && deviceWs.readyState === WebSocket.OPEN) {
        try {
          deviceWs.send(JSON.stringify({ type: 'ping' }))
        } catch (_) {}
      }
    }, 15000)
  }

  deviceWs.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      handlePushMessage(msg)
    } catch (e) {
      console.error('[Remote Desktop] Push message parse error:', e)
    }
  }

  deviceWs.onclose = (event) => {
    clearInterval(deviceWsPingInterval)
    console.log(`[Remote Desktop] Device push channel disconnected (code=${event.code})`)
    deviceWs = null
    if (event.code !== 1000) {
      scheduleWsReconnect()
    }
  }
}

function scheduleWsReconnect() {
  if (wsReconnectTimer) return
  const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts), 15000)
  wsReconnectTimer = setTimeout(() => {
    wsReconnectTimer = null
    wsReconnectAttempts++
    connectDevicePushWs()
  }, delay)
}

// Track handled request IDs so approved/rejected requests are never shown again
const handledRequestIds = new Set()

// Global callback for when request is approved or connection initiates
let onIncomingRequestCallback = null
let onSessionStartCallback = null

function setOnIncomingRequest(cb) {
  onIncomingRequestCallback = cb
}

function setOnSessionStart(cb) {
  onSessionStartCallback = cb
}

function markRequestHandled(reqId) {
  if (reqId) {
    handledRequestIds.add(reqId)
    if (!reqId.startsWith('direct-') && deviceId.value) {
      handledRequestIds.add(`direct-${deviceId.value}`)
    }
  }
}

function triggerIncomingRequest(req = {}) {
  const callerId = req.callerDeviceId || 'Remote Client'
  if (callerId && callerId === deviceId.value) {
    console.warn('[Remote Desktop] Ignored incoming request from self:', callerId)
    return
  }
  const reqId = req.requestId || 'direct-signaling'
  if (handledRequestIds.has(reqId)) {
    console.log('[Remote Desktop] Ignored already handled request in triggerIncomingRequest:', reqId)
    return
  }
  incomingRequest.value = {
    requestId: reqId,
    callerDeviceId: callerId,
    callerName: req.callerName || 'Remote Controller',
  }
  if (onIncomingRequestCallback) {
    onIncomingRequestCallback(incomingRequest.value)
  }
}

function clearIncomingRequest() {
  if (incomingRequest.value?.requestId) {
    markRequestHandled(incomingRequest.value.requestId)
  }
  incomingRequest.value = null
}

function handlePushMessage(msg) {
  if (msg.type === 'connection_request' || msg.type === 'client_waiting') {
    const callerId = msg.caller_device_id || msg.caller_connection_id || 'Remote Client'
    if (callerId && callerId === deviceId.value) {
      console.warn('[Remote Desktop] Ignored incoming request from self:', callerId)
      return
    }
    const reqId = msg.request_id || `direct-${msg.session_code || deviceId.value || 'peer'}`
    if (handledRequestIds.has(reqId)) {
      console.log('[Remote Desktop] Ignored already handled push request:', reqId)
      return
    }
    incomingRequest.value = {
      requestId: reqId,
      callerDeviceId: callerId,
      callerName: msg.caller_name || 'Remote Controller',
    }
    if (onIncomingRequestCallback) {
      onIncomingRequestCallback(incomingRequest.value)
    }
  } else if (msg.type === 'unattended_session_started') {
    console.log('[Remote Desktop] Unattended session started by:', msg.caller_device_id)
    if (onSessionStartCallback) {
      onSessionStartCallback(msg)
    }
  }
}

/**
 * Clear pending connection request on backend Redis
 */
async function clearBackendPendingRequest() {
  if (!deviceId.value) return
  const settings = loadNetworkSettings()
  try {
    await fetch(apiUrl(`/api/v1/devices/${deviceId.value}/clear-pending`, settings), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
  } catch (_) {}
}

/**
 * Accept incoming connection request
 */
async function acceptRequest(requestId) {
  if (requestId) markRequestHandled(requestId)
  const settings = loadNetworkSettings()
  try {
    const res = await fetch(apiUrl('/api/v1/sessions/approve', settings), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: requestId,
        accept: true,
        auth_token: deviceToken.value,
      }),
    })
    const data = await res.json()
    incomingRequest.value = null
    clearBackendPendingRequest().catch(() => {})
    return data
  } catch (err) {
    console.error('[Remote Desktop] Accept failed:', err)
    incomingRequest.value = null
    clearBackendPendingRequest().catch(() => {})
    throw err
  }
}

/**
 * Reject incoming connection request
 */
async function rejectRequest(requestId) {
  if (requestId) markRequestHandled(requestId)
  const settings = loadNetworkSettings()
  try {
    await fetch(apiUrl('/api/v1/sessions/approve', settings), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: requestId,
        accept: false,
        auth_token: deviceToken.value,
      }),
    })
  } catch (err) {
    console.error('[Remote Desktop] Reject failed:', err)
  } finally {
    incomingRequest.value = null
    clearBackendPendingRequest().catch(() => {})
  }
}

/**
 * Regenerate Device ID for this browser tab or app
 */
async function resetDeviceId() {
  const storage = getDeviceStorage()
  storage.removeItem(DEVICE_ID_KEY)
  storage.removeItem(DEVICE_TOKEN_KEY)
  storage.removeItem(LEGACY_ID_KEY)
  storage.removeItem(LEGACY_TOKEN_KEY)
  deviceId.value = ''
  deviceToken.value = ''
  handledRequestIds.clear()
  stopHeartbeat()
  if (deviceWs) {
    try { deviceWs.close(1000) } catch (_) {}
    deviceWs = null
  }
  return await registerDevice()
}

/**
 * Handle Network Change Event (Wi-Fi <-> Ethernet, DHCP IP change)
 */
function handleNetworkChange() {
  console.log('[Remote Desktop] Network change detected. Preserving Device ID and refreshing registration...')
  if (deviceWs && deviceWs.readyState === WebSocket.OPEN) {
    deviceWs.send(JSON.stringify({
      type: 'network_change',
      details: { timestamp: new Date().toISOString() },
    }))
  }
  registerDevice()
}

// Window network listeners
if (typeof window !== 'undefined') {
  window.addEventListener('online', handleNetworkChange)
  window.addEventListener('offline', () => {
    deviceStatus.value = 'offline'
  })
}

export function useDevice() {
  return {
    deviceId: readonly(deviceId),
    deviceToken: readonly(deviceToken),
    deviceName,
    deviceStatus: readonly(deviceStatus),
    incomingRequest: readonly(incomingRequest),
    triggerIncomingRequest,
    clearIncomingRequest,
    markRequestHandled,
    clearBackendPendingRequest,
    registerDevice,
    resetDeviceId,
    acceptRequest,
    rejectRequest,
    setOnIncomingRequest,
    setOnSessionStart,
    handleNetworkChange,
  }
}
