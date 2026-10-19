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

  const pendingAgentRequests = new Map()

  function requestAgent(actionData, timeoutMs = 15000) {
    const req_id = 'req_' + Math.random().toString(36).slice(2, 10)
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        pendingAgentRequests.delete(req_id)
        resolve({ error: 'Remote host companion agent timed out or unreachable.' })
      }, timeoutMs)
      pendingAgentRequests.set(req_id, { resolve, timer })
      signaling.send({ type: 'agent_control', data: { ...actionData, req_id } })
    })
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
      if (message.type === 'reply' || message.reply_to) {
        const reqId = message.req_id || message.data?.req_id
        if (reqId && pendingAgentRequests.has(reqId)) {
          const req = pendingAgentRequests.get(reqId)
          pendingAgentRequests.delete(reqId)
          clearTimeout(req.timer)
          req.resolve(message.data || message)
          return
        }
      }

      if (message.type === 'take_control' || (message.type === 'agent_control' && message.data?.type === 'take_control')) {
        await handleControlMessage({ type: 'take_control' })
        return
      }
      if (message.type === 'release_control' || (message.type === 'agent_control' && message.data?.type === 'release_control')) {
        await handleControlMessage({ type: 'release_control' })
        return
      }
      if ((message.type === 'agent_control' || message.type === 'control_event') && message.data) {
        await handleControlMessage(message.data)
        return
      }

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
    controlEnabled.value = false
    state.value = 'connecting'
    statusText.value = 'Connecting approved controller (View Only mode)...'
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
    controlChannel.onopen = async () => {
      let agentInfo = null
      try {
        const res = await requestAgent({ type: 'get_info' }, 2000)
        if (res && !res.error) {
          agentInfo = res
        }
      } catch (_) {}

      sendControl({
        type: 'system_info',
        device_id: sessionCode.value,
        hostname: agentInfo?.hostname || device.deviceName.value || hostLabel(),
        username: agentInfo?.username || '',
        primary_ip: agentInfo?.primary_ip || '',
        lan_ips: agentInfo?.lan_ips || [],
        os_name: agentInfo?.os_name || hostLabel(),
        platform: agentInfo?.platform || hostLabel(),
        ssh_running: !!agentInfo?.ssh_running,
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
        // 1. Try local companion agent via persistent signaling WebSocket
        try {
          const res = await requestAgent({ type: 'terminal', command: cmd }, 12000)
          if (res && !res.error) {
            const out = (res.stdout || '') + (res.stderr || '')
            const formatted = out.replace(/\r?\n/g, '\r\n')
            const promptSuffix = res.cwd ? `\x1b[1;34m${res.cwd}\x1b[0m $ ` : '$ '
            terminalChannel.send(formatted ? (formatted.endsWith('\r\n') ? formatted : formatted + '\r\n') + promptSuffix : promptSuffix)
            executed = true
          }
        } catch (_) {}

        // 2. If native desktop host
        if (!executed && isNativeApp()) {
          try {
            await invoke('write_terminal', { data: cmd + '\n' })
            executed = true
          } catch (_) {}
        }

        if (!executed) {
          terminalChannel.send('\r\n\x1b[1;33m[Host Agent Offline] Start the companion agent on the remote host to run terminal commands on this system.\x1b[0m\r\n$ ')
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
              const res = await requestAgent({ type: 'get_home' }, 5000)
              if (res && !res.error) {
                home = res.path || home
                sep = res.separator || sep
                platform = res.platform || platform
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
              const res = await requestAgent({ type: 'list', path: msg.path }, 8000)
              if (res && !res.error) {
                entries = (res.entries || []).slice(0, 300)
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

            async function readChunk(targetPath, off, sz) {
              if (isNativeApp()) {
                try {
                  return await invoke('fs_read_chunk', { filePath: targetPath, offset: off, size: sz })
                } catch (e) {
                  return { error: e.message || String(e) }
                }
              }
              return await requestAgent({ type: 'download', path: targetPath, offset: off, size: sz }, 10000)
            }

            const initial = await readChunk(msg.path, 0, chunkSize)
            if (initial && !initial.error) {
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
                const nextRes = await readChunk(msg.path, offset, chunkSize)
                if (!nextRes || nextRes.error || !nextRes.data) break
                fileChannel.send(JSON.stringify({
                  type: 'download_chunk',
                  data: nextRes.data,
                  size: nextRes.size,
                }))
                offset += nextRes.size || 0
                eof = nextRes.eof || (offset >= totalSize)
                await new Promise(r => setTimeout(r, 5))
              }

              fileChannel.send(JSON.stringify({ type: 'download_end' }))
            } else {
              fileChannel.send(JSON.stringify({ type: 'error', message: initial?.error || 'Failed to read file from remote host' }))
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
              if (isNativeApp()) {
                await invoke('fs_write_chunk', {
                  destDir: currentIncomingUpload.dest,
                  filename: currentIncomingUpload.name,
                  chunkB64: msg.data,
                  offset: msg.offset,
                })
              } else {
                await requestAgent({
                  type: 'upload_chunk',
                  dest: currentIncomingUpload.dest,
                  name: currentIncomingUpload.name,
                  data: msg.data,
                  offset: msg.offset,
                  total_size: currentIncomingUpload.size,
                }, 10000)
              }
              currentIncomingUpload.received = msg.offset + (msg.data ? Math.round(msg.data.length * 0.75) : 0)
              const pct = currentIncomingUpload.size > 0
                ? Math.min(100, Math.round((currentIncomingUpload.received / currentIncomingUpload.size) * 100))
                : 100
              fileChannel.send(JSON.stringify({
                type: 'upload_progress',
                received: currentIncomingUpload.received,
                progress: pct,
              }))
            } catch (uploadErr) {
              fileChannel.send(JSON.stringify({ type: 'error', message: uploadErr.message }))
            }
          }
        } else if (msg.type === 'upload_end') {
          currentIncomingUpload = null
          fileChannel.send(JSON.stringify({ type: 'upload_complete' }))
        } else if (msg.type === 'delete') {
          try {
            if (isNativeApp()) {
              await invoke('fs_delete', { targetPath: msg.path })
            } else {
              await requestAgent({ type: 'delete', path: msg.path }, 8000)
            }
            fileChannel.send(JSON.stringify({ type: 'delete_ok' }))
          } catch (err) {
            fileChannel.send(JSON.stringify({ type: 'error', message: 'Failed to delete file on remote host' }))
          }
        } else if (msg.type === 'mkdir') {
          try {
            if (isNativeApp()) {
              await invoke('fs_mkdir', { targetPath: msg.path })
            } else {
              await requestAgent({ type: 'mkdir', path: msg.path }, 8000)
            }
            fileChannel.send(JSON.stringify({ type: 'mkdir_ok' }))
          } catch (err) {
            fileChannel.send(JSON.stringify({ type: 'error', message: 'Failed to create directory on remote host' }))
          }
        }
      } catch (e) {
        console.error('File channel error:', e)
        fileChannel.send(JSON.stringify({ type: 'error', message: 'File channel error on remote host' }))
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
    let message
    try {
      message = typeof rawMessage === 'string' ? JSON.parse(rawMessage) : rawMessage
    } catch (_error) {
      return
    }

    try {
      // 1. Session control commands (always processed)
      if (message.type === 'take_control') {
        controlEnabled.value = true
        sendControl({ type: 'control_granted' })
        try {
          signaling.send({ type: 'control_granted' })
          signaling.send({ type: 'agent_control', data: { type: 'take_control' } })
        } catch (_) {}
        statusText.value = 'Remote user has taken control.'
        return
      }

      if (message.type === 'release_control') {
        controlEnabled.value = false
        releasePressedInput()
        sendControl({ type: 'control_released' })
        try {
          signaling.send({ type: 'control_released' })
          signaling.send({ type: 'agent_control', data: { type: 'release_control' } })
        } catch (_) {}
        statusText.value = 'Remote user released control. View only mode.'
        return
      }

      if (message.type === 'get_monitors') {
        sendControl({ type: 'monitors', list: [{ index: 1, name: 'Shared screen' }], current: 1 })
        return
      }

      if (message.type === 'chat') {
        chatMessages.value.push({
          text: message.text,
          sender: message.sender || 'client',
          timestamp: message.timestamp || new Date().toISOString(),
          delivered: true,
        })
        unreadCount.value++
        return
      }

      if (message.type === 'clipboard') {
        if (message.text) {
          if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(message.text).catch(() => {})
          }
          signaling.send({ type: 'agent_control', data: { type: 'clipboard', text: message.text } })
        }
        return
      }

      // 2. Interactive Input Events (gated by controlEnabled)
      if (!controlEnabled.value) return

      // In native desktop Tauri host, inject inputs into OS
      if (isNativeApp()) {
        if (message.type === 'mousemove') {
          await invoke('move_mouse', { x: message.x, y: message.y })
        } else if (message.type === 'mousedown' || message.type === 'mouseup' || message.type === 'click' || message.type === 'dblclick' || message.type === 'contextmenu') {
          const btn = message.type === 'contextmenu' ? 2 : (message.button ?? 0)
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
        } else if (message.type === 'scroll') {
          await invoke('scroll_mouse', {
            deltaX: scrollSteps(message.deltaX),
            deltaY: scrollSteps(message.deltaY),
          })
        } else if (message.type === 'keydown' || message.type === 'keyup') {
          await invoke('key_event', { key: message.key, isDown: message.type === 'keydown' })
          if (message.type === 'keydown') pressedKeys.add(message.key)
          else pressedKeys.delete(message.key)
        }
      }
      // Note: In browser mode, client sends directly to signaling server -> Redis -> companion agent
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
