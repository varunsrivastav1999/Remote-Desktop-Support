import { ref } from 'vue'

// Global state so it's consistent across components
const myAddress = ref('')

function generateAddress() {
  let addr = ''
  for (let i = 0; i < 9; i++) {
    addr += Math.floor(Math.random() * 10).toString()
  }
  return addr.replace(/(\d{3})(\d{3})(\d{3})/, '$1 $2 $3')
}

async function registerAddressWithBackend(addr, hostId) {
  try {
    const code = addr.replace(/\s/g, '-')
    const response = await fetch('/api/session/create/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        code, 
        status: 'waiting', 
        host_identifier: hostId
      })
    })
    if (response.ok) {
      const data = await response.json()
      // Use the actual code from server, format with spaces for UI
      if (data.code) {
        const authoritative = data.code.replace(/-/g, ' ')
        myAddress.value = authoritative
        localStorage.setItem('ad_my_address', authoritative)
      }
    }
  } catch (e) {
    console.error('Failed to register address with backend:', e)
  }
}

// Load from localStorage or generate on first launch
function initAddress() {
  if (myAddress.value) return // already initialized

  // 1. Get/Create Unique Host ID for this browser
  let hostId = localStorage.getItem('ad_host_id')
  if (!hostId) {
    hostId = 'web-' + Math.random().toString(36).substring(2, 15)
    localStorage.setItem('ad_host_id', hostId)
  }

  // 2. Get/Generate local address suggestion
  const stored = localStorage.getItem('ad_my_address')
  if (stored) {
    myAddress.value = stored
  } else {
    myAddress.value = generateAddress()
  }

  // 3. Register with backend and get authoritative code
  registerAddressWithBackend(myAddress.value, hostId)
}

export function useMyAddress() {
  initAddress()
  return { myAddress }
}
