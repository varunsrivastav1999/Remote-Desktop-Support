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
import { createFrameReceiver } from './useFrameRelay.js'

// How long to wait for a peer-to-peer path after answering before relaying through the server
const RELAY_FALLBACK_MS = 10000

const INPUT_EVENT_TYPES = new Set([
  'mousemove', 'mousedown', 'mouseup', 'click', 'dblclick', 'contextmenu', 'scroll',
  'keydown', 'keyup',
])

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
  // True while the screen arrives as frames over signaling because no peer-to-peer path exists
  const relayed = ref(false)
  let frameReceiver = null
  let rtcStream = null
  let relayTimer = null

  // ─── Control State (View Only by default) ─────────────────
  const isControlling = ref(false)
  const controlPending = ref(false)
  const controlError = ref('')
  let controlTimer = null
  // Bumped on every take/release request; the host echoes it so stale acks are ignored
  let controlSeq = 0
  // Where input goes once granted: 'host' (native host injects it, via the data channel)
  // or 'agent' (companion agent injects it, via signaling). Set by the host's grant.
  let inputRoute = null

  // ─── Authentication ──────────────────────────────────────
  const authRequired = ref(false)
  const authFailed = ref(false)

  // ─── System Info (from host) ─────────────────────────────
  const hostInfo = ref(null)
  // Issued by the server once the host approves this controller; authorizes the device's
  // system_info and SSH bridge for as long as this signaling connection lasts
  const viewerToken = ref('')

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
      console.log('[WebRTC] Connection state:', pc.connectionState)
      if (relayed.value) {
        // A late peer-to-peer path is better than the relay; otherwise the relay carries on
        if (pc.connectionState === 'connected') stopRelay()
        else return
      }
      connectionState.value = pc.connectionState

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
        startRelay()
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
      rtcStream = event.streams && event.streams.length > 0 ? event.streams[0] : new MediaStream([event.track])
      if (!relayed.value) remoteStream.value = rtcStream
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

          // Some networks have no peer-to-peer path at all (and no reachable TURN relay)
          clearTimeout(relayTimer)
          relayTimer = setTimeout(() => {
            if (peerConnection.value === pc && pc.connectionState !== 'connected') startRelay()
          }, RELAY_FALLBACK_MS)
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
        } else if (msg.type === 'frame') {
          frameReceiver?.push(msg)
        } else if (msg.type === 'session_credential') {
          viewerToken.value = msg.viewer_token || ''
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
          stopRelay(false)
          connectionState.value = 'disconnected'
          resetControlState()
        } else if (msg.type === 'permission_denied') {
          console.warn('[WebRTC] Host denied this control request')
          connectionState.value = 'failed'
          resetControlState()
          signaling.disconnect()
        } else if (msg.type === 'session_ended') {
          console.log('[WebRTC] Host ended the sharing session')
          stopRelay(false)
          connectionState.value = 'disconnected'
          resetControlState()
          signaling.disconnect()
        } else if (msg.type === 'error') {
          console.error('[WebRTC] Signaling error:', msg.message)
          connectionState.value = 'failed'
        }

        // Forward control confirmation and session updates to handleControlResponse
        if (['control_granted', 'control_released', 'control_revoked', 'control_denied', 'system_info', 'monitors', 'monitor_switched', 'quality_changed', 'chat', 'clipboard'].includes(msg.type)) {
          handleControlResponse(JSON.stringify(msg))
        } else if (msg.type === 'agent_control' || msg.type === 'reply') {
          const inner = msg.data || msg
          handleControlResponse(JSON.stringify(inner))
        } else if (msg.data && typeof msg.data === 'object' && msg.data.type) {
          handleControlResponse(JSON.stringify(msg.data))
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
          // Acks arrive on both the data channel and signaling; only honour the first one for our
          // latest request (hosts without seq support: only while a request is outstanding)
          if (isControlling.value || (data.seq === undefined ? !controlPending.value : data.seq !== controlSeq)) break
          clearControlTimer()
          controlPending.value = false
          isControlling.value = true
          controlError.value = ''
          inputRoute = data.input_route || null
          console.log(`[WebRTC] Remote machine confirmed control granted (input via ${inputRoute || 'host+agent'}) -> CONTROL ACTIVE`)
          break

        case 'control_released':
          if (!(isControlling.value || controlPending.value) || (data.seq !== undefined && data.seq !== controlSeq)) break
          clearControlTimer()
          controlPending.value = false
          isControlling.value = false
          inputRoute = null
          console.log('[WebRTC] Remote machine confirmed control released -> VIEW ONLY')
          break

        case 'control_denied':
          if (!controlPending.value || (data.seq !== undefined && data.seq !== controlSeq)) break
          clearControlTimer()
          controlPending.value = false
          isControlling.value = false
          inputRoute = null
          controlError.value = data.reason || 'Remote host denied the control request.'
          console.warn('[WebRTC] Remote host denied control:', controlError.value)
          break

        case 'control_revoked':
          clearControlTimer()
          controlPending.value = false
          isControlling.value = false
          inputRoute = null
          controlError.value = 'Remote host revoked control permissions.'
          console.log('[WebRTC] Remote host revoked control -> VIEW ONLY')
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

  /**
   * Send a message to the host peer: data channel when open, signaling relay otherwise.
   */
  function sendControl(event) {
    if (dataChannel.value && dataChannel.value.readyState === 'open') {
      try {
        dataChannel.value.send(JSON.stringify(event))
        return true
      } catch (e) {
        console.warn('[WebRTC] DataChannel send error:', e)
      }
    }
    return signaling.send({ type: 'control_event', data: event })
  }

  /**
   * Send a mouse/keyboard event to whichever side injects it on the remote machine.
   * Each event takes exactly one path, so the remote OS never receives it twice.
   */
  function sendInput(event) {
    if (!isControlling.value || !INPUT_EVENT_TYPES.has(event.type)) return false
    let sent = false
    if (inputRoute !== 'agent') sent = sendControl(event)
    // Browser hosts cannot inject OS input; their companion agent receives it via the server
    if (inputRoute !== 'host') sent = signaling.send({ type: 'agent_control', data: event }) || sent
    return sent
  }

  function clearControlTimer() {
    if (controlTimer) {
      clearTimeout(controlTimer)
      controlTimer = null
    }
  }

  // The host's control state does not survive it leaving, so drop back to View Only locally
  function resetControlState() {
    clearControlTimer()
    controlPending.value = false
    isControlling.value = false
    inputRoute = null
  }

  function sendReleaseControl() {
    controlSeq++
    const message = { type: 'release_control', seq: controlSeq }
    sendControl(message)
    // Also tell the server directly so remote input stops even if the data channel is down
    signaling.send(message)
  }

  function sendAuth(password) { return sendControl({ type: 'auth', password }) }

  function takeControl() {
    controlSeq++
    controlPending.value = true
    controlError.value = ''
    console.log('[WebRTC] Requesting Take Control from remote machine...')

    // The host decides; it answers control_granted (with the input route) or control_denied
    sendControl({ type: 'take_control', seq: controlSeq })

    clearControlTimer()
    controlTimer = setTimeout(() => {
      controlTimer = null
      if (controlPending.value && !isControlling.value) {
        controlPending.value = false
        controlError.value = 'Remote machine did not acknowledge Take Control within 4.5s. Ensure remote host or companion agent is active.'
        console.warn('[WebRTC] Take Control timed out without remote acknowledgment.')
        // If the host grants after all, make sure it does not stay in control behind our back
        sendReleaseControl()
      }
    }, 4500)

    return true
  }

  function releaseControl() {
    clearControlTimer()
    controlPending.value = false
    isControlling.value = false
    inputRoute = null
    sendReleaseControl()
    console.log('[WebRTC] Release Control sent -> VIEW ONLY')
    return true
  }

  function toggleControl() {
    return isControlling.value ? releaseControl() : takeControl()
  }

  function sendMouseEvent(type, x, y, extra = {}) {
    return sendInput({ type, x, y, ...extra })
  }

  function sendKeyEvent(type, key, modifiers = {}) {
    return sendInput({ type, key, ...modifiers })
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

  // ─── Screen relay over signaling (fallback) ──────────────

  function startRelay() {
    if (relayed.value) return
    console.warn('[WebRTC] No peer-to-peer path to the host; relaying the screen through the server')
    relayed.value = true
    frameReceiver = createFrameReceiver()
    remoteStream.value = frameReceiver.stream
    connectionState.value = 'connected'
    signaling.send({ type: 'relay_request' })
  }

  function stopRelay(notifyHost = true) {
    clearTimeout(relayTimer)
    relayTimer = null
    if (!relayed.value) return
    relayed.value = false
    if (notifyHost) signaling.send({ type: 'relay_stop' })
    frameReceiver?.stop()
    frameReceiver = null
    remoteStream.value = rtcStream
    console.log('[WebRTC] Relay stopped')
  }

  // ─── Cleanup ─────────────────────────────────────────────

  function close() {
    stopRelay(false)
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
    viewerToken.value = ''
    connectionState.value = 'disconnected'
    dataChannelState.value = 'closed'
    resetControlState()
    console.log('[WebRTC] Connection closed')
  }

  return {
    remoteStream: readonly(remoteStream),
    connectionState: readonly(connectionState),
    relayed: readonly(relayed),
    iceState: readonly(iceState),
    dataChannelState: readonly(dataChannelState),
    authRequired: readonly(authRequired),
    authFailed: readonly(authFailed),
    hostInfo: readonly(hostInfo),
    viewerToken: readonly(viewerToken),
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
    controlPending: readonly(controlPending),
    controlError: readonly(controlError),
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
