import { ref } from 'vue'

const myAddress = ref('Agent offline')
const agentStatus = ref('offline')

let pollInterval = null
let initialized = false

function formatAddress(code) {
  return code ? code.replace(/-/g, ' ') : 'Agent offline'
}

function isNativeHostSession(session) {
  return session.host_online && !session.host_identifier?.startsWith('web-')
}

async function refreshAgentAddress() {
  try {
    const response = await fetch('/api/sessions/')
    if (!response.ok) throw new Error('Address lookup failed')

    const sessions = await response.json()
    const hostSession = sessions.find(isNativeHostSession)

    if (hostSession) {
      myAddress.value = formatAddress(hostSession.code)
      agentStatus.value = hostSession.status || 'waiting'
    } else {
      myAddress.value = 'Agent offline'
      agentStatus.value = 'offline'
    }
  } catch (e) {
    myAddress.value = 'Agent offline'
    agentStatus.value = 'offline'
  }
}

function initAddress() {
  if (initialized) return
  initialized = true
  refreshAgentAddress()
  pollInterval = setInterval(refreshAgentAddress, 5000)
}

export function useMyAddress() {
  initAddress()
  return { myAddress, agentStatus, refreshAgentAddress }
}
