/**
 * useWebRTC — WebRTC composable for peer-to-peer connections.
 *
 * Handles the full WebRTC lifecycle:
 *   1. RTCPeerConnection setup with STUN servers
 *   2. SDP offer/answer creation and exchange (via signaling)
 *   3. ICE candidate gathering and exchange
 *   4. Remote video stream → <video> element binding
 *   5. RTCDataChannel for mouse/keyboard control events
 */

import { ref, readonly } from 'vue'

// Public STUN servers for NAT traversal
// Public STUN servers for NAT traversal
const ICE_SERVERS = [
  { urls: 'stun:stun.l.google.com:19302' },
  { urls: 'stun:stun1.l.google.com:19302' },
  { urls: 'stun:stun2.l.google.com:19302' },
  { urls: 'stun:stun3.l.google.com:19302' },
  { urls: 'stun:stun4.l.google.com:19302' },
  { urls: 'stun:stun.ekiga.net' },
  { urls: 'stun:stun.ideasip.com' },
  { urls: 'stun:stun.rixtelecom.se' },
  { urls: 'stun:stun.schlund.de' },
  { urls: 'stun:stun.voiparound.com' },
  { urls: 'stun:stun.voipbuster.com' },
  { urls: 'stun:stun.voipstunt.com' },
  { urls: 'stun:stun.voxgratia.org' },
]

export function useWebRTC(signaling) {
  const peerConnection = ref(null)
  const dataChannel = ref(null)
  const remoteStream = ref(null)
  const connectionState = ref('new')    // new | connecting | connected | disconnected | failed
  const iceState = ref('new')
  const dataChannelState = ref('closed') // closed | connecting | open

  /**
   * Initialize the WebRTC peer connection as the CLIENT (viewer).
   *
   * The client:
   *   1. Creates an RTCPeerConnection
   *   2. Waits for the host's SDP offer (received via signaling)
   *   3. Sets remote description, creates answer, sends it back
   *   4. Exchanges ICE candidates
   *   5. Receives the remote video stream
   *   6. Opens a data channel for control input
   */
  function initAsClient(customSettings = {}) {
    console.log('[WebRTC] Initializing as CLIENT')

    const iceServers = [...ICE_SERVERS]
    if (customSettings.stunServers) {
      customSettings.stunServers.split('\n').forEach(s => {
        if (s.trim()) iceServers.push({ urls: s.trim() })
      })
    }
    if (customSettings.turnServers) {
      customSettings.turnServers.split('\n').forEach(s => {
        if (s.trim()) iceServers.push({ urls: s.trim() })
      })
    }

    const rtcConfig = { iceServers }
    if (customSettings.alwaysRelay) {
      rtcConfig.iceTransportPolicy = 'relay'
    }

    const pc = new RTCPeerConnection(rtcConfig)
    peerConnection.value = pc

    // ─── ICE candidate handling ──────────────────────────
    pc.onicecandidate = (event) => {
      if (event.candidate) {
        console.log('[WebRTC] Sending ICE candidate')
        signaling.sendIceCandidate(event.candidate.toJSON())
      }
    }

    // ─── Connection state ────────────────────────────────
    pc.onconnectionstatechange = () => {
      connectionState.value = pc.connectionState
      console.log('[WebRTC] Connection state:', pc.connectionState)
      
      if (pc.connectionState === 'failed') {
        handleIceFailure()
      }
    }

    pc.oniceconnectionstatechange = () => {
      iceState.value = pc.iceConnectionState
      console.log('[WebRTC] ICE state:', pc.iceConnectionState)
      
      if (pc.iceConnectionState === 'failed') {
        handleIceFailure()
      }
    }

    /**
     * Handle ICE connection failure by triggering a restart.
     */
    async function handleIceFailure() {
      console.warn('[WebRTC] ICE connection failed. Attempting restart...')
      try {
        // Only the client (caller) typically initiates restart in our flow
        // But since the host is the caller in our flow, the client should wait for a new offer
        // or we can explicitly request one.
        signaling.send({ type: 'ice_restart_request' })
      } catch (err) {
        console.error('[WebRTC] Failed to initiate ICE restart:', err)
      }
    }

    // ─── Remote stream (video from host agent) ──────────
    pc.ontrack = (event) => {
      console.log('[WebRTC] Received remote track:', event.track.kind)
      if (event.streams && event.streams.length > 0) {
        remoteStream.value = event.streams[0]
      } else {
        if (!remoteStream.value) remoteStream.value = new MediaStream()
        remoteStream.value.addTrack(event.track)
      }
    }

    // ─── Data channel (for mouse/keyboard control) ──────
    pc.ondatachannel = (event) => {
      console.log('[WebRTC] Received data channel:', event.channel.label)
      setupDataChannel(event.channel)
    }

    // Also create a data channel from client side
    const dc = pc.createDataChannel('control', { ordered: true })
    setupDataChannel(dc)

    // ─── Handle signaling messages ──────────────────────
    const iceCandidateQueue = []

    signaling.onMessage(async (msg) => {
      try {
        if (msg.type === 'offer') {
          console.log('[WebRTC] Received SDP offer, creating answer...')
          
          // If this is a restart, we should be ready for it
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
        } else if (msg.type === 'peer_joined') {
          console.log(`[WebRTC] Peer joined as ${msg.role}`)
        } else if (msg.type === 'peer_left') {
          console.log(`[WebRTC] Peer left (${msg.role})`)
          connectionState.value = 'disconnected'
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
    }

    dc.onclose = () => {
      console.log('[WebRTC] Data channel CLOSED')
      dataChannelState.value = 'closed'
    }

    dc.onerror = (err) => {
      console.error('[WebRTC] Data channel error:', err)
    }
  }

  function sendControl(event) {
    if (dataChannel.value && dataChannel.value.readyState === 'open') {
      dataChannel.value.send(JSON.stringify(event))
      return true
    }
    return false
  }

  function sendMouseEvent(type, x, y, extra = {}) { return sendControl({ type, x, y, ...extra }) }
  function sendKeyEvent(type, key, modifiers = {}) { return sendControl({ type, key, ...modifiers }) }

  function close() {
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
    console.log('[WebRTC] Connection closed')
  }

  return {
    remoteStream: readonly(remoteStream),
    connectionState: readonly(connectionState),
    iceState: readonly(iceState),
    dataChannelState: readonly(dataChannelState),
    initAsClient,
    sendControl,
    sendMouseEvent,
    sendKeyEvent,
    close,
  }
}
