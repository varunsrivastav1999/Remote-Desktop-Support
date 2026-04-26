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

async function registerAddressWithBackend(addr) {
  try {
    const code = addr.replace(/\s/g, '-')
    await fetch('/api/session/create/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        code, 
        status: 'waiting', 
        host_identifier: 'Web Client' 
      })
    })
  } catch (e) {
    console.error('Failed to register address with backend:', e)
  }
}

// Load from localStorage or generate on first launch
function initAddress() {
  if (myAddress.value) return // already initialized

  const stored = localStorage.getItem('ad_my_address')
  if (stored) {
    myAddress.value = stored
  } else {
    myAddress.value = generateAddress()
    localStorage.setItem('ad_my_address', myAddress.value)
  }

  // Register with backend so it is connectable
  registerAddressWithBackend(myAddress.value)
}

export function useMyAddress() {
  initAddress()
  return { myAddress }
}
