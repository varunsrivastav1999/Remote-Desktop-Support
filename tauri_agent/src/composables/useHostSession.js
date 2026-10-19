import { invoke } from '@tauri-apps/api/core'
import { readonly, ref } from 'vue'
import { apiUrl, loadNetworkSettings, isNativeApp, getDefaultIceServers } from './serverConfig.js'
import { useScreenShare } from './useScreenShare.js'
import { useSignaling } from './useSignaling.js'
import { useDevice } from './useDevice.js'

function rtcConfiguration(settings) {
  const iceServers = getDefaultIceServers(settings)
  const configuration = { iceServers }
  if (settings.alwaysRelay) configuration.iceTransportPolicy = 'relay'
  return configuration
}

function hostLabel() {
  return navigator.userAgentData?.platform || navigator.platform || 'Desktop'
}

function createHostSession() {
  const signaling = useSignaling()
  const screenShare = useScreenShare()
  const device = useDevice()

  const sessionCode = ref('')
  const state = ref('idle')
  const statusText = ref('Connecting to signaling server...')
  const error = ref('')
  const pendingController = ref(false)
  const incomingCallerName = ref('')
  const incomingCallerId = ref('')
  const controlEnabled = ref(false)

  let settings = {}
  let hostToken = ''
  let peerConnection = null
  let controlChannel = null
  let terminalChannel = null
  let terminalPollInterval = null
  let fileChannel = null
  let queuedIce = []
  let onlinePromise = null
  const pressedButtons = new Set()
  const pressedKeys = new Set()

  async function ensureOnline() {
    if (sessionCode.value && device.deviceStatus.value === 'online' && signaling.isConnected.value) return true
    if (onlinePromise) return onlinePromise

    onlinePromise = registerDesk()
    try {
      return await onlinePromise
    } finally {
      onlinePromise = null
    }
  }

  async function registerDesk() {
    error.value = ''
    settings = loadNetworkSettings()
    state.value = 'registering'
    statusText.value = 'Registering permanent Device ID...'

    try {
      let registered = await device.registerDevice()
      if (!registered || !device.deviceId.value) {
        await new Promise(r => setTimeout(r, 1000))
        registered = await device.registerDevice()
      }

      if (!registered || !device.deviceId.value) {
        throw new Error('Could not register device with signaling server.')
      }

      sessionCode.value = device.deviceId.value
      hostToken = device.deviceToken.value
      statusText.value = `Device ID ${sessionCode.value} online.`

      // Set listener for push connection requests
      device.setOnIncomingRequest((req) => {
        if (req.callerDeviceId && req.callerDeviceId === sessionCode.value) {
          console.warn('[HostSession] Ignored incoming request from self:', req.callerDeviceId)
          return
        }
        pendingController.value = true
        incomingCallerName.value = req.callerName
        incomingCallerId.value = req.callerDeviceId
        state.value = 'approval'
        statusText.value = `Incoming request from ${req.callerName} (${req.callerDeviceId})`
      })

      // Set listener for unattended session start
      device.setOnSessionStart(async (msg) => {
        statusText.value = `Unattended session connected from ${msg.caller_device_id}`
        await allowController(true)
      })

      signaling.onMessage(handleSignalingMessage)
      signaling.onOpen(() => signaling.register('host', hostToken))
      signaling.onClose((event) => {
        if (sessionCode.value && event.code !== 1000 && event.code !== 1001) {
          state.value = 'registering'
          statusText.value = 'Reconnecting signaling...'
        }
      })
      signaling.connect(sessionCode.value, settings.signalingServer || '')
      return true
    } catch (registerError) {
      state.value = 'idle'
      error.value = registerError.message
      statusText.value = 'Could not connect to signaling server.'
      return false
    }
  }

  async function start() {
    if (screenShare.localStream.value) return true

    error.value = ''
    state.value = 'selecting'
    statusText.value = 'Select the screen or window you want to share.'
    const stream = await screenShare.startScreenShare({ preferDisplay: 'monitor' })
    if (!stream) {
      state.value = pendingController.value ? 'approval' : 'online'
      error.value = screenShare.shareError.value || 'Screen sharing could not be started.'
      statusText.value = pendingController.value
        ? 'Select a screen before approving controller.'
        : 'Online. Screen access starts only after your approval.'
      return false
    }

    state.value = pendingController.value ? 'approval' : 'waiting'
    statusText.value = pendingController.value
      ? 'A controller is waiting. Allow control when ready.'
      : 'Screen selected. Ready for incoming connections.'
    return true
  }

  async function handleSignalingMessage(message) {
    try {
      if (message.type === 'registered' && message.role === 'host') {
        error.value = ''
        state.value = screenShare.localStream.value ? 'waiting' : 'online'
        statusText.value = screenShare.localStream.value
          ? 'Screen selected. Ready for incoming connections.'
          : 'Online. Screen access starts only after your approval.'
      } else if (message.type === 'peer_joined' && message.role === 'client') {
        const callerId = message.caller_device_id || message.client_device_id || 'Remote Client'
        if (callerId === sessionCode.value) {
          console.warn('[HostSession] Ignored peer_joined from self:', callerId)
          return
        }

        pendingController.value = true
        incomingCallerName.value = message.caller_name || 'Remote Controller'
        incomingCallerId.value = callerId
        state.value = 'approval'
        statusText.value = `A remote controller (${incomingCallerName.value}) is requesting access.`

        device.triggerIncomingRequest?.({
          requestId: `direct-${sessionCode.value || 'peer'}`,
          callerDeviceId: incomingCallerId.value,
          callerName: incomingCallerName.value,
        })

        // If screen is ALREADY shared, automatically send offer immediately
        if (screenShare.localStream.value) {
          console.log('[HostSession] Screen stream active, automatically starting WebRTC offer...')
          await allowController(true)
        }
      } else if (message.type === 'answer' && peerConnection) {
        await peerConnection.setRemoteDescription(new RTCSessionDescription(message.sdp))
        while (queuedIce.length) {
          await peerConnection.addIceCandidate(new RTCIceCandidate(queuedIce.shift()))
        }
      } else if (message.type === 'ice') {
        if (peerConnection?.remoteDescription) {
          await peerConnection.addIceCandidate(new RTCIceCandidate(message.candidate))
        } else {
          queuedIce.push(message.candidate)
        }
      } else if (message.type === 'peer_left' && message.role === 'client') {
        closePeer()
        pendingController.value = false
        controlEnabled.value = false
        state.value = screenShare.localStream.value ? 'waiting' : 'online'
        statusText.value = screenShare.localStream.value
          ? 'Controller disconnected. Ready for a new request.'
          : 'Online. Screen access starts only after your approval.'
      } else if (message.type === 'error') {
        error.value = message.message
      }
    } catch (signalError) {
      error.value = `Connection negotiation failed: ${signalError.message}`
    }
  }

  async function allowController(skipScreenCheck = false) {
    if (!skipScreenCheck && !pendingController.value) return
    if (!screenShare.localStream.value && !await start()) return
    pendingController.value = false
    device.clearIncomingRequest?.()
    controlEnabled.value = true
    state.value = 'connecting'
    statusText.value = 'Connecting approved controller...'
    closePeer()

    // Ensure signaling is online & connected
    if (!signaling.isConnected.value) {
      await ensureOnline()
      for (let i = 0; i < 30 && !signaling.isConnected.value; i++) {
        await new Promise(r => setTimeout(r, 100))
      }
    }

    peerConnection = new RTCPeerConnection(rtcConfiguration(settings))
    for (const track of screenShare.localStream.value.getTracks()) {
      peerConnection.addTrack(track, screenShare.localStream.value)
    }

    peerConnection.onicecandidate = (event) => {
      if (event.candidate) signaling.sendIceCandidate(event.candidate.toJSON())
    }
    peerConnection.onconnectionstatechange = () => {
      if (!peerConnection) return
      if (peerConnection.connectionState === 'connected') {
        state.value = 'connected'
        statusText.value = 'Remote desktop active. Controlling permitted.'
      } else if (['failed', 'disconnected'].includes(peerConnection.connectionState)) {
        state.value = 'waiting'
        statusText.value = 'Connection ended. Ready for a new request.'
        controlEnabled.value = false
      }
    }

    // ─── Control Data Channel ──────────────────────────────
    controlChannel = peerConnection.createDataChannel('control', { ordered: true })
    controlChannel.onopen = () => {
      sendControl({
        type: 'system_info',
        hostname: device.deviceName.value || hostLabel(),
        platform: hostLabel(),
        monitors: [{ index: 1, name: 'Shared screen' }],
        current_monitor: 1,
        quality: 'medium',
      })
    }
    controlChannel.onmessage = (event) => handleControlMessage(event.data)

    // ─── Terminal Data Channel ─────────────────────────────
    terminalChannel = peerConnection.createDataChannel('terminal', { ordered: true })
    terminalChannel.onopen = async () => {
      console.log('[Remote Desktop Host] Terminal channel OPEN')
      if (isNativeApp()) {
        try {
          await invoke('start_terminal')
          startTerminalPolling()
        } catch (e) {
          console.warn('[Remote Desktop Host] Native terminal start:', e)
        }
      } else {
        terminalChannel.send('\x1b[1;32mRemote Desktop Interactive Shell Connected.\x1b[0m\r\n$ ')
      }
    }
    terminalChannel.onmessage = async (event) => {
      if (isNativeApp()) {
        try {
          await invoke('write_terminal', { data: event.data })
        } catch (e) {
          console.warn('write_terminal error:', e)
        }
      } else {
        if (event.data === '\r') terminalChannel.send('\r\n$ ')
        else terminalChannel.send(event.data)
      }
    }
    terminalChannel.onclose = () => {
      stopTerminalPolling()
      if (isNativeApp()) invoke('close_terminal').catch(() => {})
    }

    // ─── File Transfer Data Channel ────────────────────────
    fileChannel = peerConnection.createDataChannel('file-transfer', { ordered: true })
    fileChannel.onopen = () => console.log('[Remote Desktop Host] File transfer channel OPEN')
    fileChannel.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'get_home') {
          let home = '/'
          if (isNativeApp()) {
            home = await invoke('fs_get_home').catch(() => '/')
          }
          fileChannel.send(JSON.stringify({ type: 'home', path: home, separator: '/', platform: hostLabel() }))
        } else if (msg.type === 'list') {
          let entries = []
          if (isNativeApp()) {
            entries = await invoke('fs_list_dir', { dirPath: msg.path }).catch(() => [])
          }
          fileChannel.send(JSON.stringify({ type: 'listing', path: msg.path, entries }))
        }
      } catch (e) {
        console.error('File channel error:', e)
      }
    }

    const offer = await peerConnection.createOffer()
    await peerConnection.setLocalDescription(offer)
    signaling.sendOffer({ type: offer.type, sdp: offer.sdp })
  }

  function startTerminalPolling() {
    stopTerminalPolling()
    terminalPollInterval = setInterval(async () => {
      if (terminalChannel?.readyState === 'open' && isNativeApp()) {
        try {
          const out = await invoke('read_terminal')
          if (out) terminalChannel.send(out)
        } catch (_) {}
      }
    }, 50)
  }

  function stopTerminalPolling() {
    if (terminalPollInterval) {
      clearInterval(terminalPollInterval)
      terminalPollInterval = null
    }
  }

  function denyController() {
    signaling.send({ type: 'permission_denied' })
    if (device.incomingRequest.value) {
      device.rejectRequest(device.incomingRequest.value.requestId).catch(() => {})
    }
    device.clearIncomingRequest?.()
    pendingController.value = false
    state.value = screenShare.localStream.value ? 'waiting' : 'online'
    statusText.value = screenShare.localStream.value
      ? 'Access denied. Screen still ready to share.'
      : 'Access denied. Screen sharing remains off.'
  }

  async function handleControlMessage(rawMessage) {
    if (!controlEnabled.value) return
    let message
    try {
      message = JSON.parse(rawMessage)
    } catch (_error) {
      return
    }

    try {
      if (message.type === 'mousemove') {
        if (isNativeApp()) await invoke('move_mouse', { x: message.x, y: message.y })
      } else if (message.type === 'mousedown' || message.type === 'mouseup') {
        if (isNativeApp()) {
          await invoke('move_mouse', { x: message.x, y: message.y })
          await invoke('mouse_event', { button: message.button, isDown: message.type === 'mousedown' })
        }
        if (message.type === 'mousedown') pressedButtons.add(message.button)
        else pressedButtons.delete(message.button)
      } else if (message.type === 'scroll') {
        if (isNativeApp()) {
          await invoke('scroll_mouse', {
            deltaX: scrollSteps(message.deltaX),
            deltaY: scrollSteps(message.deltaY),
          })
        }
      } else if (message.type === 'keydown' || message.type === 'keyup') {
        if (isNativeApp()) {
          await invoke('key_event', { key: message.key, isDown: message.type === 'keydown' })
        }
        if (message.type === 'keydown') pressedKeys.add(message.key)
        else pressedKeys.delete(message.key)
      } else if (message.type === 'clipboard') {
        if (message.text && navigator.clipboard && window.isSecureContext) {
          navigator.clipboard.writeText(message.text).catch(() => {})
        }
      } else if (message.type === 'get_monitors') {
        sendControl({ type: 'monitors', list: [{ index: 1, name: 'Shared screen' }], current: 1 })
      } else if (message.type === 'chat') {
        sendControl({ ...message, sender: 'client' })
      }
    } catch (_invokeError) {
      error.value = 'Remote input needs native app permissions.'
    }
  }

  function sendControl(message) {
    if (controlChannel?.readyState === 'open') {
      controlChannel.send(JSON.stringify(message))
    }
  }

  function scrollSteps(delta = 0) {
    if (!delta) return 0
    return Math.sign(delta) * Math.max(1, Math.round(Math.abs(delta) / 60))
  }

  function releasePressedInput() {
    if (isNativeApp()) {
      for (const button of pressedButtons) {
        invoke('mouse_event', { button, isDown: false }).catch(() => {})
      }
      for (const key of pressedKeys) {
        invoke('key_event', { key, isDown: false }).catch(() => {})
      }
    }
    pressedButtons.clear()
    pressedKeys.clear()
  }

  function closePeer() {
    releasePressedInput()
    stopTerminalPolling()
    if (controlChannel) {
      controlChannel.close()
      controlChannel = null
    }
    if (terminalChannel) {
      terminalChannel.close()
      terminalChannel = null
    }
    if (fileChannel) {
      fileChannel.close()
      fileChannel = null
    }
    if (peerConnection) {
      peerConnection.close()
      peerConnection = null
    }
    queuedIce = []
  }

  function stopSharing() {
    if (pendingController.value || controlEnabled.value) {
      signaling.send({ type: 'session_ended' })
    }
    closePeer()
    screenShare.stopScreenShare()
    pendingController.value = false
    controlEnabled.value = false
    if (sessionCode.value) {
      state.value = 'online'
      statusText.value = 'Online. Screen sharing is off.'
    }
  }

  function disconnect() {
    stopSharing()
    signaling.disconnect()
    sessionCode.value = ''
    hostToken = ''
    state.value = 'idle'
    statusText.value = 'This desk is offline.'
  }

  return {
    localStream: screenShare.localStream,
    sessionCode: readonly(sessionCode),
    state: readonly(state),
    statusText: readonly(statusText),
    error: readonly(error),
    pendingController: readonly(pendingController),
    incomingCallerName: readonly(incomingCallerName),
    incomingCallerId: readonly(incomingCallerId),
    controlEnabled: readonly(controlEnabled),
    signalingConnected: signaling.isConnected,
    ensureOnline,
    start,
    stopSharing,
    disconnect,
    allowController,
    denyController,
  }
}

let sharedHostSession = null

export function useHostSession() {
  if (!sharedHostSession) sharedHostSession = createHostSession()
  return sharedHostSession
}
