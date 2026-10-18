export function isNativeApp() {
  return Boolean(window.__TAURI_INTERNALS__ || window.__TAURI__)
}

export function loadNetworkSettings() {
  const defaults = {
    signalingServer: isNativeApp() ? 'ws://localhost:8000/ws/' : '',
  }
  try {
    const stored = localStorage.getItem('ad_settings')
    return stored ? { ...defaults, ...JSON.parse(stored) } : defaults
  } catch (_error) {
    return defaults
  }
}

export function apiUrl(path, settings = loadNetworkSettings()) {
  const signalingServer = (settings?.signalingServer || '').trim()

  // In browser: if no custom signaling server is configured, use relative path (proxied by Nginx)
  if (!isNativeApp()) {
    if (!signalingServer) {
      return path
    }
    try {
      const source = /^[a-z][a-z\d+\-.]*:\/\//i.test(signalingServer)
        ? signalingServer
        : `ws://${signalingServer}`
      const parsed = new URL(source)
      if (typeof window !== 'undefined' && parsed.host === window.location.host) {
        return path
      }
    } catch (_) {
      return path
    }
  }

  if (!signalingServer) {
    return path
  }

  try {
    const source = /^[a-z][a-z\d+\-.]*:\/\//i.test(signalingServer)
      ? signalingServer
      : `ws://${signalingServer}`
    const url = new URL(source)
    url.protocol = url.protocol === 'wss:' || url.protocol === 'https:' ? 'https:' : 'http:'
    url.pathname = path
    url.search = ''
    url.hash = ''
    return url.toString()
  } catch (_e) {
    return path
  }
}

export function getDefaultIceServers(settings = {}) {
  const iceServers = [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
    { urls: 'stun:stun2.l.google.com:19302' },
  ]

  // Add self-hosted coturn STUN/TURN from current host
  if (typeof window !== 'undefined' && window.location?.hostname) {
    const host = window.location.hostname
    if (host) {
      iceServers.push({ urls: `stun:${host}:3478` })
      iceServers.push({
        urls: `turn:${host}:3478?transport=udp`,
        username: 'remote',
        credential: 'support_2026',
      })
      iceServers.push({
        urls: `turn:${host}:3478?transport=tcp`,
        username: 'remote',
        credential: 'support_2026',
      })
    }
  }

  // Add custom STUN servers from settings
  if (settings.stunServers) {
    settings.stunServers.split('\n').forEach(s => {
      if (s.trim()) iceServers.push({ urls: s.trim() })
    })
  }

  // Add custom TURN servers from settings
  if (settings.turnServers) {
    settings.turnServers.split('\n').forEach(s => {
      if (s.trim()) {
        const turnServer = { urls: s.trim() }
        if (settings.turnUsername) turnServer.username = settings.turnUsername
        if (settings.turnPassword) turnServer.credential = settings.turnPassword
        iceServers.push(turnServer)
      }
    })
  }

  return iceServers
}


