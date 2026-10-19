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
  const chatMessages = ref([])
  const unreadCount = ref(0)
  const hasAgent = ref(isNativeApp())

  let settings = {}
  let hostToken = ''
  let peerConnection = null
  let controlChannel = null
  let terminalChannel = null
  let terminalPollInterval = null
  let fileChannel = null
  let queuedIce = []
  let onlinePromise = null
  let currentIncomingUpload = null
  let agentPollTimer = null
  const pressedButtons = new Set()
  const pressedKeys = new Set()

  async function checkAgentStatus() {
    if (isNativeApp()) {
      hasAgent.value = true
      return true
    }
    // Check direct local companion daemon first
    try {
      const local = await fetch('http://127.0.0.1:8765/health', { signal: AbortSignal.timeout(1000) })
      if (local && local.ok) {
        hasAgent.value = true
        return true
      }
    } catch (_) {}

    // Check backend agent presence for this device
    if (sessionCode.value) {
      try {
        const res = await fetch(apiUrl(`/api/v1/devices/${sessionCode.value}/agent_status`, settings), { signal: AbortSignal.timeout(2000) })
        if (res && res.ok) {
          const d = await res.json()
          hasAgent.value = Boolean(d.agent_online)
          return hasAgent.value
        }
      } catch (_) {}
    }
    hasAgent.value = false
    return false
  }

  function startAgentPolling() {
    stopAgentPolling()
    checkAgentStatus()
    agentPollTimer = setInterval(checkAgentStatus, 3000)
  }

  function stopAgentPolling() {
    if (agentPollTimer) {
      clearInterval(agentPollTimer)
      agentPollTimer = null
    }
  }

  async function callAgent(endpoint, method = 'POST', data = null) {
    const cleanPath = endpoint.replace(/^\//, '')
    const body = data ? JSON.stringify(data) : undefined
    const headers = data ? { 'Content-Type': 'application/json' } : {}

    // 1. Direct local companion agent (fastest, 1.2s timeout)
    try {
      const directUrl = `http://127.0.0.1:8765/${cleanPath}`
      const res = await fetch(directUrl, { method, headers, body, signal: AbortSignal.timeout(1200) })
      if (res && res.ok) return res
    } catch (_) {}

    // 2. HTTPS agent proxy via backend (3s timeout)
    try {
      const url = apiUrl(`/api/v1/agent/${cleanPath}`, settings)
      const res = await fetch(url, { method, headers, body, signal: AbortSignal.timeout(3000) })
      if (res && res.ok) return res
    } catch (_) {}

    return null
  }

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
      startAgentPolling()

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

        // If host is already connected and controlling, ignore duplicate peer_joined
        if (controlEnabled.value || state.value === 'connected') {
          console.log('[HostSession] Already connected with peer, ignoring duplicate peer_joined')
          return
        }

        pendingController.value = true
        incomingCallerName.value = message.caller_name || 'Remote Controller'
        incomingCallerId.value = callerId
        state.value = 'approval'
        statusText.value = `A remote controller (${incomingCallerName.value}) is requesting access.`

        const reqId = message.request_id || `direct-${sessionCode.value || 'peer'}`
        device.triggerIncomingRequest?.({
          requestId: reqId,
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
    let terminalLineBuffer = ''
    terminalChannel = peerConnection.createDataChannel('terminal', { ordered: true })
    terminalChannel.onopen = async () => {
      console.log('[Remote Desktop Host] Terminal channel OPEN')
      if (isNativeApp()) {
        try {
          await invoke('start_terminal')
          startTerminalPolling()
          return
        } catch (e) {
          console.warn('[Remote Desktop Host] Native terminal start:', e)
        }
      }
      terminalChannel.send('\x1b[1;32mRemote Desktop Interactive Shell Connected.\x1b[0m\r\n$ ')
    }

    terminalChannel.onmessage = async (event) => {
      if (isNativeApp()) {
        try {
          await invoke('write_terminal', { data: event.data })
          return
        } catch (e) {
          console.warn('write_terminal fallback to interactive shell runner:', e)
        }
      }

      // Interactive Shell Runner (Browser mode & Companion Agent / Backend fallback)
      const char = event.data
      if (char === '\r') {
        // Enter pressed
        terminalChannel.send('\r\n')
        const cmd = terminalLineBuffer.trim()
        terminalLineBuffer = ''

        if (!cmd) {
          terminalChannel.send('$ ')
          return
        }

        if (cmd === 'clear') {
          terminalChannel.send('\x1b[2J\x1b[H$ ')
          return
        }

        let executed = false
        // 1. Try local companion agent first (executes on host OS)
        try {
          const localRes = await callAgent('terminal', 'POST', { command: cmd })
          if (localRes && localRes.ok) {
            const d = await localRes.json()
            const out = (d.stdout || '') + (d.stderr || '')
            const formatted = out.replace(/\r?\n/g, '\r\n')
            terminalChannel.send(formatted ? (formatted.endsWith('\r\n') ? formatted : formatted + '\r\n') + '$ ' : '$ ')
            executed = true
          }
        } catch (_) {}

        // 2. Fallback to backend terminal runner
        if (!executed) {
          try {
            const apiRes = await fetch(apiUrl('/api/v1/terminal/exec', settings), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ command: cmd }),
              signal: AbortSignal.timeout(15000),
            })
            if (apiRes.ok) {
              const d = await apiRes.json()
              const out = (d.stdout || '') + (d.stderr || '')
              const formatted = out.replace(/\r?\n/g, '\r\n')
              terminalChannel.send(formatted ? (formatted.endsWith('\r\n') ? formatted : formatted + '\r\n') + '$ ' : '$ ')
              executed = true
            }
          } catch (_) {}
        }

        if (!executed) {
          terminalChannel.send('Failed to execute command: local agent and backend unreachable.\r\n$ ')
        }
      } else if (char === '\x7f' || char === '\b') {
        // Backspace
        if (terminalLineBuffer.length > 0) {
          terminalLineBuffer = terminalLineBuffer.slice(0, -1)
          terminalChannel.send('\b \b')
        }
      } else if (char === '\x03') {
        // Ctrl+C
        terminalLineBuffer = ''
        terminalChannel.send('^C\r\n$ ')
      } else {
        // Regular characters
        terminalLineBuffer += char
        terminalChannel.send(char)
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
          let sep = '/'
          let platform = hostLabel()
          if (isNativeApp()) {
            home = await invoke('fs_get_home').catch(() => '/')
          } else {
            try {
              const res = await callAgent('fs/home', 'GET')
              if (res && res.ok) {
                const data = await res.json()
                home = data.path || home
                sep = data.separator || sep
                platform = data.platform || platform
              }
            } catch (_) {}
          }
          fileChannel.send(JSON.stringify({ type: 'home', path: home, separator: sep, platform }))
        } else if (msg.type === 'list') {
          let entries = []
          if (isNativeApp()) {
            entries = await invoke('fs_list_dir', { dirPath: msg.path }).catch(() => [])
          } else {
            try {
              const res = await callAgent('fs/list', 'POST', { path: msg.path })
              if (res && res.ok) {
                const data = await res.json()
                entries = data.entries || []
              }
            } catch (_) {}
          }
          fileChannel.send(JSON.stringify({ type: 'listing', path: msg.path, entries }))
        } else if (msg.type === 'download') {
          try {
            let offset = 0
            const chunkSize = 48 * 1024
            let totalSize = 0
            let fileName = msg.path.split('/').pop().split('\\').pop()
            let eof = false

            const res = await callAgent('fs/read_chunk', 'POST', { path: msg.path, offset: 0, size: chunkSize })
            if (res && res.ok) {
              const initial = await res.json()
              fileName = initial.name || fileName
              totalSize = initial.total_size || 0
              fileChannel.send(JSON.stringify({
                type: 'download_start',
                name: fileName,
                size: totalSize,
              }))

              if (initial.data) {
                fileChannel.send(JSON.stringify({
                  type: 'download_chunk',
                  data: initial.data,
                  size: initial.size,
                }))
              }
              offset += initial.size || 0
              eof = initial.eof || (offset >= totalSize)

              while (!eof && offset < totalSize) {
                const nextRes = await callAgent('fs/read_chunk', 'POST', { path: msg.path, offset, size: chunkSize })
                if (!nextRes || !nextRes.ok) break
                const chunkData = await nextRes.json()
                if (!chunkData.data) break
                fileChannel.send(JSON.stringify({
                  type: 'download_chunk',
                  data: chunkData.data,
                  size: chunkData.size,
                }))
                offset += chunkData.size
                eof = chunkData.eof || (offset >= totalSize)
                await new Promise(r => setTimeout(r, 10))
              }

              fileChannel.send(JSON.stringify({ type: 'download_end' }))
            } else {
              fileChannel.send(JSON.stringify({ type: 'error', message: 'Failed to read file from host' }))
            }
          } catch (err) {
            fileChannel.send(JSON.stringify({ type: 'error', message: err.message }))
          }
        } else if (msg.type === 'upload_start') {
          currentIncomingUpload = {
            name: msg.name,
            size: msg.size,
            dest: msg.dest,
            received: 0,
          }
          fileChannel.send(JSON.stringify({ type: 'upload_ready' }))
        } else if (msg.type === 'upload_chunk') {
          if (currentIncomingUpload) {
            try {
              await callAgent('fs/write_chunk', 'POST', {
                dest: currentIncomingUpload.dest,
                name: currentIncomingUpload.name,
                data: msg.data,
                offset: msg.offset,
              })
              currentIncomingUpload.received = msg.offset + (msg.data ? Math.round(msg.data.length * 0.75) : 0)
              const pct = currentIncomingUpload.size > 0
                ? Math.min(100, Math.round((currentIncomingUpload.received / currentIncomingUpload.size) * 100))
                : 100
              fileChannel.send(JSON.stringify({
                type: 'upload_progress',
                received: currentIncomingUpload.received,
                progress: pct,
              }))
            } catch (_) {}
          }
        } else if (msg.type === 'upload_end') {
          currentIncomingUpload = null
          fileChannel.send(JSON.stringify({ type: 'upload_complete' }))
        } else if (msg.type === 'delete') {
          try {
            await callAgent('fs/delete', 'POST', { path: msg.path })
            fileChannel.send(JSON.stringify({ type: 'delete_ok' }))
          } catch (err) {
            fileChannel.send(JSON.stringify({ type: 'error', message: 'Failed to delete file' }))
          }
        } else if (msg.type === 'mkdir') {
          try {
            await callAgent('fs/mkdir', 'POST', { path: msg.path })
            fileChannel.send(JSON.stringify({ type: 'mkdir_ok' }))
          } catch (err) {
            fileChannel.send(JSON.stringify({ type: 'error', message: 'Failed to create directory' }))
          }
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
        if (isNativeApp()) {
          await invoke('move_mouse', { x: message.x, y: message.y })
        } else {
          signaling.send({ type: 'agent_control', data: message })
          callAgent('mouse', 'POST', message)
        }
      } else if (message.type === 'mousedown' || message.type === 'mouseup' || message.type === 'click' || message.type === 'dblclick' || message.type === 'contextmenu') {
        const btn = message.type === 'contextmenu' ? 2 : (message.button ?? 0)
        const payload = { ...message, button: btn }
        if (isNativeApp()) {
          await invoke('move_mouse', { x: message.x, y: message.y })
          if (message.type === 'mousedown') {
            await invoke('mouse_event', { button: btn, isDown: true })
            pressedButtons.add(btn)
          } else if (message.type === 'mouseup') {
            await invoke('mouse_event', { button: btn, isDown: false })
            pressedButtons.delete(btn)
          } else if (message.type === 'click' || message.type === 'contextmenu') {
            await invoke('mouse_event', { button: btn, isDown: true })
            await invoke('mouse_event', { button: btn, isDown: false })
          } else if (message.type === 'dblclick') {
            await invoke('mouse_event', { button: btn, isDown: true })
            await invoke('mouse_event', { button: btn, isDown: false })
            await new Promise(r => setTimeout(r, 40))
            await invoke('mouse_event', { button: btn, isDown: true })
            await invoke('mouse_event', { button: btn, isDown: false })
          }
        } else {
          signaling.send({ type: 'agent_control', data: payload })
          callAgent('mouse', 'POST', payload)
        }
      } else if (message.type === 'scroll') {
        if (isNativeApp()) {
          await invoke('scroll_mouse', {
            deltaX: scrollSteps(message.deltaX),
            deltaY: scrollSteps(message.deltaY),
          })
        } else {
          signaling.send({ type: 'agent_control', data: message })
          callAgent('mouse', 'POST', message)
        }
      } else if (message.type === 'keydown' || message.type === 'keyup') {
        if (isNativeApp()) {
          await invoke('key_event', { key: message.key, isDown: message.type === 'keydown' })
          if (message.type === 'keydown') pressedKeys.add(message.key)
          else pressedKeys.delete(message.key)
        } else {
          signaling.send({ type: 'agent_control', data: message })
          callAgent('key', 'POST', message)
        }
      } else if (message.type === 'clipboard') {
        if (message.text && navigator.clipboard && window.isSecureContext) {
          navigator.clipboard.writeText(message.text).catch(() => {})
        }
      } else if (message.type === 'get_monitors') {
        sendControl({ type: 'monitors', list: [{ index: 1, name: 'Shared screen' }], current: 1 })
      } else if (message.type === 'chat') {
        chatMessages.value.push({
          text: message.text,
          sender: message.sender || 'client',
          timestamp: message.timestamp || new Date().toISOString(),
          delivered: true,
        })
        unreadCount.value++
      }
    } catch (_invokeError) {
      error.value = 'Remote input needs native app permissions.'
    }
  }

  function sendChat(text) {
    if (!text || !text.trim()) return
    const msg = {
      type: 'chat',
      text: text.trim(),
      sender: 'host',
      timestamp: new Date().toISOString(),
    }
    sendControl(msg)
    chatMessages.value.push({ ...msg, delivered: true })
  }

  function markChatRead() {
    unreadCount.value = 0
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
    stopAgentPolling()
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
    stopAgentPolling()
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
    hasAgent: readonly(hasAgent),
    chatMessages,
    unreadCount,
    sendChat,
    markChatRead,
    ensureOnline,
    checkAgentStatus,
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
