/**
 * useSignaling — WebSocket composable for signaling server communication.
 *
 * Manages the WebSocket connection to the Django Channels backend,
 * sending and receiving signaling messages (register, offer, answer, ICE).
 */

import { ref, readonly } from 'vue'

export function useSignaling() {
  const socket = ref(null)
  const isConnected = ref(false)
  const error = ref(null)
  
  let currentSessionCode = null
  let currentSignalingServer = ''
  let reconnectTimer = null
  let reconnectAttempts = 0
  let heartbeatTimer = null

  // Event callbacks
  let onMessageCallback = null
  let onOpenCallback = null
  let onCloseCallback = null

  /**
   * Connect to the signaling WebSocket for a given session code.
   */
  function connect(sessionCode, signalingServer = '') {
    currentSessionCode = sessionCode
    currentSignalingServer = signalingServer
    if (socket.value) {
      disconnect(false) // Don't stop auto-reconnect if it's already running
    }

    let url
    try {
      url = buildSignalingUrl(sessionCode, signalingServer)
    } catch (err) {
      error.value = err.message
      scheduleReconnect()
      return
    }

    console.log(`[Signaling] Connecting to ${url} (Attempt ${reconnectAttempts + 1})`)
    error.value = null

    try {
      socket.value = new WebSocket(url)
    } catch (err) {
      error.value = `Failed to create WebSocket: ${err.message}`
      scheduleReconnect()
      return
    }

    socket.value.onopen = () => {
      console.log('[Signaling] Connected')
      isConnected.value = true
      reconnectAttempts = 0
      startHeartbeat()
      onOpenCallback?.()
    }

    socket.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'pong') return // Heartbeat response
        onMessageCallback?.(data)
      } catch (err) {
        console.error('[Signaling] Failed to parse message:', err)
      }
    }

    socket.value.onclose = (event) => {
      console.log(`[Signaling] Disconnected (code=${event.code})`)
      isConnected.value = false
      stopHeartbeat()
      
      // Don't reconnect if it was a clean close by the user
      if (event.code !== 1000 && event.code !== 1001) {
        scheduleReconnect()
      }
      
      onCloseCallback?.(event)
    }

    socket.value.onerror = (event) => {
      console.error('[Signaling] WebSocket error')
      error.value = 'WebSocket connection error'
    }
  }

  function scheduleReconnect() {
    if (reconnectTimer) return
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000)
    console.log(`[Signaling] Scheduling reconnect in ${delay}ms...`)
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      reconnectAttempts++
      if (currentSessionCode) connect(currentSessionCode, currentSignalingServer)
    }, delay)
  }

  function startHeartbeat() {
    stopHeartbeat()
    heartbeatTimer = setInterval(() => {
      send({ type: 'ping' })
    }, 25000) // Every 25 seconds
  }

  function stopHeartbeat() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function disconnect(fullStop = true) {
    if (fullStop) {
      currentSessionCode = null
      currentSignalingServer = ''
      reconnectAttempts = 0
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
    }
    
    stopHeartbeat()
    if (socket.value) {
      socket.value.close(1000) // Normal closure
      socket.value = null
    }
    isConnected.value = false
  }

  function send(message) {
    if (!socket.value || socket.value.readyState !== WebSocket.OPEN) return false
    socket.value.send(JSON.stringify(message))
    return true
  }

  function register(role) { return send({ type: 'register', role }) }
  function sendOffer(sdp) { return send({ type: 'offer', sdp }) }
  function sendAnswer(sdp) { return send({ type: 'answer', sdp }) }
  function sendIceCandidate(candidate) { return send({ type: 'ice', candidate }) }

  function onMessage(callback) { onMessageCallback = callback }
  function onOpen(callback) { onOpenCallback = callback }
  function onClose(callback) { onCloseCallback = callback }

  function buildSignalingUrl(sessionCode, signalingServer = '') {
    const customServer = signalingServer.trim()
    if (customServer) {
      return buildCustomSignalingUrl(customServer, sessionCode)
    }

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host = window.location.host
    return `${protocol}://${host}/ws/signaling/${sessionCode}/`
  }

  function buildCustomSignalingUrl(rawUrl, sessionCode) {
    const codeToken = '__SESSION_CODE__'
    const preparedUrl = rawUrl.replace('{code}', codeToken)
    const hasProtocol = /^[a-z][a-z\d+\-.]*:\/\//i.test(rawUrl)
    const url = new URL(hasProtocol ? preparedUrl : `ws://${preparedUrl}`)

    if (url.protocol === 'http:') url.protocol = 'ws:'
    if (url.protocol === 'https:') url.protocol = 'wss:'
    if (!['ws:', 'wss:'].includes(url.protocol)) {
      throw new Error('Signaling Server URL must use ws://, wss://, http://, or https://')
    }

    const basePath = url.pathname.replace(/\/+$/, '')
    if (url.pathname.includes(codeToken)) {
      url.pathname = url.pathname.replace(codeToken, sessionCode)
    } else if (basePath.endsWith('/ws/signaling')) {
      url.pathname = `${basePath}/${sessionCode}/`
    } else if (basePath.includes('/ws/signaling/')) {
      url.pathname = basePath.replace(/\/[^/]+$/, `/${sessionCode}/`)
    } else {
      url.pathname = `/ws/signaling/${sessionCode}/`
    }
    url.search = ''
    return url.toString()
  }

  return {
    isConnected: readonly(isConnected),
    error: readonly(error),
    connect,
    disconnect,
    register,
    send,
    sendOffer,
    sendAnswer,
    sendIceCandidate,
    onMessage,
    onOpen,
    onClose,
  }
}
