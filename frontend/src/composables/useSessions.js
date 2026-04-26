import { ref, computed } from 'vue'

const sessions = ref([])
const loading = ref(true)
const favIds = ref(new Set())
const history = ref([]) // Local connection history
let pollInterval = null

export function useSessions() {
  const fetchSessions = async () => {
    try {
      const response = await fetch('/api/sessions/')
      if (response.ok) {
        sessions.value = await response.json()
      }
    } catch (e) {
      console.error('Failed to fetch sessions:', e)
    } finally {
      loading.value = false
    }
  }

  const loadHistory = () => {
    const stored = localStorage.getItem('ad_connection_history')
    if (stored) {
      try {
        history.value = JSON.parse(stored)
      } catch (e) {
        history.value = []
      }
    }
  }

  const addToHistory = (session) => {
    // Remove if already exists to move to top
    const newHistory = history.value.filter(s => s.code !== session.code)
    newHistory.unshift({
      ...session,
      last_connected: new Date().toISOString()
    })
    // Keep last 10
    history.value = newHistory.slice(0, 10)
    localStorage.setItem('ad_connection_history', JSON.stringify(history.value))
  }

  const clearHistory = () => {
    history.value = []
    localStorage.removeItem('ad_connection_history')
  }

  const startPolling = (interval = 8000) => {
    if (pollInterval) return
    fetchSessions()
    pollInterval = setInterval(fetchSessions, interval)
  }

  const stopPolling = () => {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }

  const renameSession = async (code, newAlias) => {
    // Optimistic update locally
    const session = sessions.value.find(s => s.code === code)
    if (session) {
      session.alias = newAlias
    }

    try {
      const response = await fetch(`/api/session/${code}/rename/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alias: newAlias })
      })
      if (response.ok) {
        const updated = await response.json()
        // Update with true data from server
        const idx = sessions.value.findIndex(s => s.code === code)
        if (idx !== -1) sessions.value[idx] = updated
      }
    } catch (e) {
      console.error('Failed to rename session:', e)
      // Re-fetch to correct optimistic update on failure
      fetchSessions()
    }
  }

  const removeSessionLocally = (id) => {
    sessions.value = sessions.value.filter(s => s.id !== id)
  }

  const toggleFav = (session) => {
    const f = new Set(favIds.value)
    if (f.has(session.id)) {
      f.delete(session.id)
    } else {
      f.add(session.id)
    }
    favIds.value = f
  }

  const favSessions = computed(() => {
    return sessions.value.filter(s => favIds.value.has(s.id))
  })

  // helper to safely get the alias or fallback to host_identifier
  const getDisplayName = (session) => {
    if (session.alias && session.alias.trim() !== '') return session.alias
    if (session.host_identifier && session.host_identifier.trim() !== '') return session.host_identifier
    return 'Unknown'
  }

  return {
    sessions,
    loading,
    favIds,
    favSessions,
    history,
    fetchSessions,
    loadHistory,
    addToHistory,
    clearHistory,
    startPolling,
    stopPolling,
    renameSession,
    removeSessionLocally,
    toggleFav,
    getDisplayName
  }
}
