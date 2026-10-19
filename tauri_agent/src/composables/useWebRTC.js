/**
 * useWebRTC — WebRTC composable for peer-to-peer connections.
 *
 * Handles the full WebRTC lifecycle:
 *   1. RTCPeerConnection setup with STUN/TURN servers
 *   2. SDP offer/answer creation and exchange (via signaling)
 *   3. ICE candidate gathering and exchange
 *   4. Remote video stream → <video> element binding
 *   5. RTCDataChannel for mouse/keyboard control events
 *   6. Connection statistics (latency, FPS, bitrate)
 *   7. Clipboard synchronization
 *   8. In-session chat
 *   9. Quality preset switching
 *   10. Multi-monitor management
 */

import { ref, readonly, reactive } from 'vue'
import { getDefaultIceServers } from './serverConfig.js'

export function useWebRTC(signaling) {
  const peerConnection = ref(null)
  const dataChannel = ref(null)
  const fileChannel = ref(null)
  const terminalChannel = ref(null)
  const remoteStream = ref(null)
  const connectionState = ref('new')    // new | connecting | connected | disconnected | failed
  const iceState = ref('new')
  const dataChannelState = ref('closed') // closed | connecting | open
  const offerReceived = ref(false)
  const waitingForHost = ref(true)

  // ─── Control State (View Only by default) ─────────────────
  const isControlling = ref(false)

  // ─── Authentication ──────────────────────────────────────
  const authRequired = ref(false)
  const authFailed = ref(false)

  // ─── System Info (from host) ─────────────────────────────
  const hostInfo = ref(null)

  // ─── Connection Stats ────────────────────────────────────
  const stats = reactive({
    latency: 0,
    fps: 0,
    bitrate: 0,
    bitrateFormatted: '0 KB/s',
    resolution: '',
    codec: '',
    connectionType: '',
    candidateType: '',
    packetsLost: 0,
    jitter: 0,
  })
  let statsInterval = null
  let prevBytesReceived = 0
  let prevTimestamp = 0

  // ─── Chat ────────────────────────────────────────────────
  const chatMessages = ref([])
  const unreadCount = ref(0)
  let chatVisible = false

  // ─── Clipboard ───────────────────────────────────────────
  const lastClipboard = ref('')

  // ─── Monitors ────────────────────────────────────────────
  const monitors = ref([])
  const currentMonitor = ref(1)

  // ─── Quality ─────────────────────────────────────────────
  const currentQuality = ref('medium')

  /**
   * Initialize the WebRTC peer connection as the CLIENT (viewer).
   */
  function initAsClient(customSettings = {}) {
    console.log('[WebRTC] Initializing as CLIENT')

    const iceServers = getDefaultIceServers(customSettings)
    const rtcConfig = { iceServers }
    if (customSettings.alwaysRelay) {
      rtcConfig.iceTransportPolicy = 'relay'
    }

    const pc = new RTCPeerConnection(rtcConfig)
    peerConnection.value = pc

    // ─── ICE candidate handling ──────────────────────────
    pc.onicecandidate = (event) => {
      if (event.candidate) {
        signaling.sendIceCandidate(event.candidate.toJSON())
      }
    }

    // ─── Connection state ────────────────────────────────
    pc.onconnectionstatechange = () => {
      connectionState.value = pc.connectionState
      console.log('[WebRTC] Connection state:', pc.connectionState)

      if (pc.connectionState === 'connected') {
        startStatsPolling()
      } else if (pc.connectionState === 'failed') {
        handleIceFailure()
      } else if (pc.connectionState === 'disconnected') {
        stopStatsPolling()
      }
    }

    pc.oniceconnectionstatechange = () => {
      iceState.value = pc.iceConnectionState
      console.log('[WebRTC] ICE state:', pc.iceConnectionState)

      if (['connected', 'completed'].includes(pc.iceConnectionState)) {
        connectionState.value = 'connected'
      }

      if (pc.iceConnectionState === 'failed') {
        handleIceFailure()
      }
    }

    async function handleIceFailure() {
      console.warn('[WebRTC] ICE connection failed. Attempting restart...')
      try {
        signaling.send({ type: 'ice_restart_request' })
      } catch (err) {
        console.error('[WebRTC] Failed to initiate ICE restart:', err)
      }
    }

    // ─── Remote stream (video from host agent) ──────────
    pc.ontrack = (event) => {
      console.log('[WebRTC] Received remote track:', event.track.kind, event.track.id)
      event.track.enabled = true
      if (event.streams && event.streams.length > 0) {
        remoteStream.value = event.streams[0]
      } else {
        remoteStream.value = new MediaStream([event.track])
      }
      connectionState.value = 'connected'
    }

    // ─── Data channel (for mouse/keyboard control) ──────
    pc.ondatachannel = (event) => {
      console.log('[WebRTC] Received data channel:', event.channel.label)
      if (event.channel.label === 'control') {
        setupDataChannel(event.channel)
      } else if (event.channel.label === 'file-transfer') {
        setupFileChannel(event.channel)
      } else if (event.channel.label === 'terminal') {
        setupTerminalChannel(event.channel)
      }
    }

    // ─── Handle signaling messages ──────────────────────
    const iceCandidateQueue = []

    signaling.onMessage(async (msg) => {
      try {
        if (msg.type === 'offer') {
          console.log('[WebRTC] Received SDP offer, creating answer...')
          offerReceived.value = true
          waitingForHost.value = false

          await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp))

          while (iceCandidateQueue.length > 0) {
            const candidate = iceCandidateQueue.shift()
            await pc.addIceCandidate(new RTCIceCandidate(candidate))
          }

          const answer = await pc.createAnswer()
          await pc.setLocalDescription(answer)
          signaling.sendAnswer({
            type: answer.type,
            sdp: answer.sdp,
          })
        } else if (msg.type === 'answer') {
          console.log('[WebRTC] Received SDP answer')
          await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp))

          while (iceCandidateQueue.length > 0) {
            const candidate = iceCandidateQueue.shift()
            await pc.addIceCandidate(new RTCIceCandidate(candidate))
          }
        } else if (msg.type === 'ice') {
          if (pc.remoteDescription && pc.remoteDescription.type) {
            await pc.addIceCandidate(new RTCIceCandidate(msg.candidate))
          } else {
            iceCandidateQueue.push(msg.candidate)
          }
        } else if (msg.type === 'waiting_for_host') {
          console.log('[WebRTC] Signaling room ready, waiting for remote host to start stream...')
          connectionState.value = 'connecting'
        } else if (msg.type === 'peer_joined') {
          console.log(`[WebRTC] Peer joined as ${msg.role}`)
          if (msg.role === 'host') {
            connectionState.value = 'connecting'
          }
        } else if (msg.type === 'peer_left') {
          console.log(`[WebRTC] Peer left (${msg.role})`)
          connectionState.value = 'disconnected'
        } else if (msg.type === 'permission_denied') {
          console.warn('[WebRTC] Host denied this control request')
          connectionState.value = 'failed'
          signaling.disconnect()
        } else if (msg.type === 'session_ended') {
          console.log('[WebRTC] Host ended the sharing session')
          connectionState.value = 'disconnected'
          signaling.disconnect()
        } else if (msg.type === 'error') {
          console.error('[WebRTC] Signaling error:', msg.message)
          connectionState.value = 'failed'
        }
      } catch (err) {
        console.error('[WebRTC] Error handling signaling message:', err)
      }
    })

    return pc
  }

  /**
   * Set up the RTCDataChannel for sending control events.
   */
  function setupDataChannel(dc) {
    dataChannel.value = dc

    dc.onopen = () => {
      console.log('[WebRTC] Data channel OPEN')
      dataChannelState.value = 'open'
      // Request monitor list from host
      sendControl({ type: 'get_monitors' })
    }

    dc.onclose = () => {
      console.log('[WebRTC] Data channel CLOSED')
      dataChannelState.value = 'closed'
    }

    dc.onmessage = (event) => {
      handleControlResponse(event.data)
    }

    dc.onerror = (err) => {
      console.error('[WebRTC] Data channel error:', err)
    }
  }

  /**
   * Set up the file transfer data channel.
   */
  function setupFileChannel(dc) {
    fileChannel.value = dc
    console.log('[WebRTC] File transfer channel ready')
  }

  /**
   * Set up the terminal data channel.
   */
  let terminalMessageCallback = null
  function setupTerminalChannel(dc) {
    terminalChannel.value = dc
    dc.onopen = () => console.log('[WebRTC] Terminal channel OPEN')
    dc.onmessage = (event) => {
      if (terminalMessageCallback) {
        terminalMessageCallback(event.data)
      }
    }
    dc.onclose = () => console.log('[WebRTC] Terminal channel CLOSED')
  }

  function setTerminalCallback(callback) {
    terminalMessageCallback = callback
  }

  function sendTerminalData(data) {
    if (terminalChannel.value && terminalChannel.value.readyState === 'open') {
      terminalChannel.value.send(data)
    }
  }

  /**
   * Handle responses from the host on the control data channel.
   */
  function handleControlResponse(rawData) {
    try {
      const data = JSON.parse(rawData)

      switch (data.type) {
        case 'auth_required':
          authRequired.value = true
          break

        case 'auth_result':
          if (data.status === 'success') {
            authRequired.value = false
            authFailed.value = false
          } else {
            authFailed.value = true
          }
          break

        case 'system_info':
          hostInfo.value = data
          monitors.value = data.monitors || []
          currentMonitor.value = data.current_monitor || 1
          currentQuality.value = data.quality || 'medium'
          console.log('[WebRTC] Host info received:', data.hostname, data.platform)
          break

        case 'monitors':
          monitors.value = data.list || []
          currentMonitor.value = data.current || 1
          break

        case 'monitor_switched':
          currentMonitor.value = data.index
          console.log(`[WebRTC] Monitor switched to ${data.index} (${data.width}x${data.height})`)
          break

        case 'quality_changed':
          currentQuality.value = data.preset
          console.log(`[WebRTC] Quality changed to: ${data.preset}`)
          break

        case 'clipboard':
          lastClipboard.value = data.text || ''
          // Try to write to browser clipboard
          if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(data.text).catch(() => {})
          }
          break

        case 'chat':
          chatMessages.value.push({
            text: data.text,
            sender: data.sender || 'host',
            timestamp: data.timestamp || new Date().toISOString(),
            delivered: data.delivered || false,
          })
          if (!chatVisible) {
            unreadCount.value++
          }
          break

        case 'host_stats':
          // Merge host-side stats
          stats.hostFps = data.fps
          stats.hostQuality = data.quality
          stats.hostResolution = data.resolution
          break

        case 'control_granted':
          isControlling.value = true
          console.log('[WebRTC] Host confirmed control granted -> CONTROL ACTIVE')
          break

        case 'control_released':
          isControlling.value = false
          console.log('[WebRTC] Host confirmed control released -> VIEW ONLY')
          break

        case 'control_revoked':
          isControlling.value = false
          console.log('[WebRTC] Host revoked control -> VIEW ONLY')
          break

        default:
          // Unknown control message, ignore
          break
      }
    } catch (e) {
      // Not JSON, ignore
    }
  }

  // ─── Control Methods ─────────────────────────────────────

  function sendControl(event) {
    if (dataChannel.value && dataChannel.value.readyState === 'open') {
      dataChannel.value.send(JSON.stringify(event))
      return true
    }
    return false
  }

  function sendAuth(password) { return sendControl({ type: 'auth', password }) }

  function takeControl() {
    isControlling.value = true
    sendControl({ type: 'take_control' })
    console.log('[WebRTC] Take Control sent -> isControlling = true')
    return true
  }

  function releaseControl() {
    isControlling.value = false
    sendControl({ type: 'release_control' })
    console.log('[WebRTC] Release Control sent -> isControlling = false')
    return true
  }

  function toggleControl() {
    return isControlling.value ? releaseControl() : takeControl()
  }

  function sendMouseEvent(type, x, y, extra = {}) {
    if (!isControlling.value) return false
    return sendControl({ type, x, y, ...extra })
  }

  function sendKeyEvent(type, key, modifiers = {}) {
    if (!isControlling.value) return false
    return sendControl({ type, key, ...modifiers })
  }

  // ─── Quality ─────────────────────────────────────────────

  function setQuality(preset) {
    currentQuality.value = preset
    return sendControl({ type: 'quality', preset })
  }

  // ─── Multi-Monitor ──────────────────────────────────────

  function switchMonitor(index) {
    return sendControl({ type: 'switch_monitor', index })
  }

  function requestMonitors() {
    return sendControl({ type: 'get_monitors' })
  }

  // ─── Clipboard ───────────────────────────────────────────

  function sendClipboard(text) {
    lastClipboard.value = text
    return sendControl({ type: 'clipboard', text: text.slice(0, 50000) })
  }

  // ─── Chat ────────────────────────────────────────────────

  function sendChat(text) {
    const msg = {
      type: 'chat',
      text,
      sender: 'client',
      timestamp: new Date().toISOString(),
    }
    sendControl(msg)
    // Add to local messages immediately
    chatMessages.value.push({
      ...msg,
      delivered: false,
    })
  }

  function setChatVisible(visible) {
    chatVisible = visible
    if (visible) unreadCount.value = 0
  }

  // ─── Stats Polling ───────────────────────────────────────

  function startStatsPolling() {
    stopStatsPolling()
    prevBytesReceived = 0
    prevTimestamp = 0
    statsInterval = setInterval(pollStats, 1000)
  }

  function stopStatsPolling() {
    if (statsInterval) {
      clearInterval(statsInterval)
      statsInterval = null
    }
  }

  async function pollStats() {
    const pc = peerConnection.value
    if (!pc) return

    try {
      const report = await pc.getStats()
      report.forEach(s => {
        if (s.type === 'inbound-rtp' && s.kind === 'video') {
          // FPS
          stats.fps = s.framesPerSecond || 0

          // Resolution
          if (s.frameWidth && s.frameHeight) {
            stats.resolution = `${s.frameWidth}×${s.frameHeight}`
          }

          // Bitrate
          const now = s.timestamp
          if (prevTimestamp && s.bytesReceived) {
            const timeDiff = (now - prevTimestamp) / 1000
            const bytesDiff = s.bytesReceived - prevBytesReceived
            if (timeDiff > 0) {
              stats.bitrate = Math.round((bytesDiff * 8) / timeDiff)
              const kbps = stats.bitrate / 1000
              if (kbps > 1000) {
                stats.bitrateFormatted = `${(kbps / 1000).toFixed(1)} Mbps`
              } else {
                stats.bitrateFormatted = `${Math.round(kbps)} Kbps`
              }
            }
          }
          prevBytesReceived = s.bytesReceived || 0
          prevTimestamp = now

          // Packets lost
          stats.packetsLost = s.packetsLost || 0
          stats.jitter = s.jitter || 0

          // Codec
          if (s.codecId) {
            report.forEach(c => {
              if (c.id === s.codecId) {
                stats.codec = c.mimeType?.split('/')[1]?.toUpperCase() || ''
              }
            })
          }
        }

        if (s.type === 'candidate-pair' && s.state === 'succeeded') {
          stats.latency = Math.round(s.currentRoundTripTime * 1000) || 0

          // Get connection type
          if (s.remoteCandidateId) {
            report.forEach(rc => {
              if (rc.id === s.remoteCandidateId) {
                stats.candidateType = rc.candidateType || ''
                stats.connectionType = rc.candidateType === 'relay' ? 'Relay (TURN)' :
                  rc.candidateType === 'srflx' ? 'STUN (P2P)' :
                    rc.candidateType === 'host' ? 'Direct (LAN)' : rc.candidateType
              }
            })
          }
        }
      })
    } catch (e) {
      // Stats not available yet
    }
  }

  // ─── Cleanup ─────────────────────────────────────────────

  function close() {
    stopStatsPolling()
    if (terminalChannel.value) {
      terminalChannel.value.close()
      terminalChannel.value = null
    }
    if (fileChannel.value) {
      fileChannel.value.close()
      fileChannel.value = null
    }
    if (dataChannel.value) {
      dataChannel.value.close()
      dataChannel.value = null
    }
    if (peerConnection.value) {
      peerConnection.value.close()
      peerConnection.value = null
    }
    remoteStream.value = null
    connectionState.value = 'disconnected'
    dataChannelState.value = 'closed'
    isControlling.value = false
    console.log('[WebRTC] Connection closed')
  }

  return {
    remoteStream: readonly(remoteStream),
    connectionState: readonly(connectionState),
    iceState: readonly(iceState),
    dataChannelState: readonly(dataChannelState),
    authRequired: readonly(authRequired),
    authFailed: readonly(authFailed),
    hostInfo: readonly(hostInfo),
    stats,
    chatMessages,
    unreadCount,
    lastClipboard: readonly(lastClipboard),
    monitors: readonly(monitors),
    currentMonitor: readonly(currentMonitor),
    currentQuality: readonly(currentQuality),
    fileChannel: readonly(fileChannel),
    offerReceived: readonly(offerReceived),
    waitingForHost: readonly(waitingForHost),
    isControlling: readonly(isControlling),
    takeControl,
    releaseControl,
    toggleControl,
    initAsClient,
    sendControl,
    sendAuth,
    sendMouseEvent,
    sendKeyEvent,
    setQuality,
    switchMonitor,
    requestMonitors,
    sendClipboard,
    sendChat,
    setChatVisible,
    sendTerminalData,
    setTerminalCallback,
    close,
  }
}
