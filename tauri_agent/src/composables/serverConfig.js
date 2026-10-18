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
  // When running in a standard web browser, always use relative path so Nginx reverse proxies it
  if (!isNativeApp()) {
    return path
  }

  const signalingServer = (settings.signalingServer || '').trim()
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

