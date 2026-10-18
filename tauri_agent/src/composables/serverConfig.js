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


