import { computed, ref } from 'vue'
import { useDevice } from './useDevice.js'

const overrideAddress = ref('')
const overrideStatus = ref('')

export function setHostedAddress(code, status = 'online') {
  overrideAddress.value = code
  overrideStatus.value = status
}

export function clearHostedAddress() {
  overrideAddress.value = ''
  overrideStatus.value = 'offline'
}

export function useMyAddress() {
  const device = useDevice()

  const myAddress = computed(() => {
    if (overrideAddress.value) return overrideAddress.value
    if (device.deviceId.value) return device.deviceId.value
    return 'Connecting...'
  })

  const agentStatus = computed(() => {
    if (overrideStatus.value) return overrideStatus.value
    return device.deviceStatus.value || 'offline'
  })

  return {
    myAddress,
    agentStatus,
    setHostedAddress,
    clearHostedAddress,
  }
}
