/**
 * useFileTransfer — Composable for file transfer over WebRTC Data Channel.
 *
 * Handles:
 *   1. Remote directory listing/browsing
 *   2. File download from remote host (chunked)
 *   3. File upload to remote host (chunked via FileReader)
 *   4. Transfer progress tracking
 *   5. Queue system for multiple transfers
 */

import { ref, reactive, readonly } from 'vue'

const CHUNK_SIZE = 48 * 1024 // 48KB chunks

export function useFileTransfer(fileChannel) {
  const remotePath = ref('')
  const remoteEntries = ref([])
  const remotePlatform = ref('')
  const separator = ref('/')
  const isLoading = ref(false)
  const errorMessage = ref('')
  let homeTimeout = null
  let listTimeout = null

  // Transfer queue
  const transfers = ref([])
  const activeTransfer = reactive({
    name: '',
    direction: '',  // 'upload' | 'download'
    progress: 0,
    size: 0,
    received: 0,
    speed: '',
  })

  // Download assembly
  let downloadChunks = []
  let downloadName = ''
  let downloadSize = 0
  let downloadStartTime = 0
  let activeChannel = null

  function getChannel() {
    if (activeChannel && activeChannel.readyState === 'open') return activeChannel
    const ch = (fileChannel && typeof fileChannel === 'object' && 'value' in fileChannel) ? fileChannel.value : fileChannel
    if (ch && ch.readyState === 'open') return ch
    return activeChannel || ch
  }

  /**
   * Listen for messages on the file transfer channel.
   */
  function setupChannel(dc) {
    if (!dc) return
    activeChannel = dc

    dc.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleMessage(data)
      } catch (e) {
        console.error('[FileTransfer] Parse error:', e)
      }
    }

    errorMessage.value = ''
    if (dc.readyState === 'open') {
      isLoading.value = true
      send(dc, { type: 'get_home' })
      if (homeTimeout) clearTimeout(homeTimeout)
      homeTimeout = setTimeout(() => {
        if (isLoading.value) {
          isLoading.value = false
          if (!remotePath.value) {
            errorMessage.value = 'Remote filesystem connection timed out. Ensure remote companion agent is active.'
          }
        }
      }, 5000)
    } else {
      dc.onopen = () => {
        isLoading.value = true
        errorMessage.value = ''
        send(dc, { type: 'get_home' })
        if (homeTimeout) clearTimeout(homeTimeout)
        homeTimeout = setTimeout(() => {
          if (isLoading.value) {
            isLoading.value = false
            if (!remotePath.value) {
              errorMessage.value = 'Remote filesystem connection timed out.'
            }
          }
        }, 5000)
      }
      dc.onerror = () => {
        isLoading.value = false
        errorMessage.value = 'DataChannel error during file transfer.'
      }
      dc.onclose = () => {
        isLoading.value = false
      }
    }
  }

  function handleMessage(data) {
    if (homeTimeout) {
      clearTimeout(homeTimeout)
      homeTimeout = null
    }
    if (listTimeout) {
      clearTimeout(listTimeout)
      listTimeout = null
    }
    errorMessage.value = ''

    switch (data.type) {
      case 'home':
        remotePath.value = data.path
        separator.value = data.separator || '/'
        remotePlatform.value = data.platform || ''
        // Auto-list the home directory
        listDirectory(data.path)
        break

      case 'listing':
        remotePath.value = data.path
        remoteEntries.value = data.entries || []
        isLoading.value = false
        break

      case 'download_start':
        downloadChunks = []
        downloadName = data.name
        downloadSize = data.size
        downloadStartTime = Date.now()
        activeTransfer.name = data.name
        activeTransfer.direction = 'download'
        activeTransfer.size = data.size
        activeTransfer.received = 0
        activeTransfer.progress = 0
        break

      case 'download_chunk':
        const chunk = base64ToUint8Array(data.data)
        downloadChunks.push(chunk)
        activeTransfer.received += data.size
        activeTransfer.progress = Math.min(100, Math.round(activeTransfer.received / downloadSize * 100))
        updateSpeed()
        break

      case 'download_end':
        finalizeDownload()
        break

      case 'upload_ready':
        // Host is ready, start sending chunks (handled in uploadFile)
        break

      case 'upload_progress':
        activeTransfer.received = data.received
        activeTransfer.progress = data.progress
        updateSpeed()
        break

      case 'upload_complete':
        activeTransfer.progress = 100
        activeTransfer.name = ''
        // Refresh directory listing
        listDirectory(remotePath.value)
        break

      case 'mkdir_ok':
      case 'delete_ok':
        listDirectory(remotePath.value)
        break

      case 'error':
        console.error('[FileTransfer] Error:', data.message)
        isLoading.value = false
        errorMessage.value = data.message || 'File operation failed on remote host'
        activeTransfer.name = ''
        break
    }
  }

  function finalizeDownload() {
    // Assemble all chunks into a Blob and trigger browser download
    const blob = new Blob(downloadChunks)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = downloadName
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    activeTransfer.progress = 100
    setTimeout(() => {
      activeTransfer.name = ''
      activeTransfer.progress = 0
    }, 2000)

    downloadChunks = []
  }

  function updateSpeed() {
    const elapsed = (Date.now() - downloadStartTime) / 1000
    if (elapsed > 0 && activeTransfer.received > 0) {
      const bytesPerSec = activeTransfer.received / elapsed
      if (bytesPerSec > 1024 * 1024) {
        activeTransfer.speed = `${(bytesPerSec / (1024 * 1024)).toFixed(1)} MB/s`
      } else if (bytesPerSec > 1024) {
        activeTransfer.speed = `${(bytesPerSec / 1024).toFixed(0)} KB/s`
      } else {
        activeTransfer.speed = `${Math.round(bytesPerSec)} B/s`
      }
    }
  }

  // ─── Actions ──────────────────────────────────────────────

  function listDirectory(path) {
    isLoading.value = true
    errorMessage.value = ''
    const dc = getChannel()
    if (dc && dc.readyState === 'open') {
      send(dc, { type: 'list', path })
      if (listTimeout) clearTimeout(listTimeout)
      listTimeout = setTimeout(() => {
        if (isLoading.value) {
          console.warn('[FileTransfer] Directory listing timed out')
          isLoading.value = false
          errorMessage.value = 'Remote directory listing timed out.'
        }
      }, 4500)
    } else {
      isLoading.value = false
      errorMessage.value = 'File transfer channel is not connected.'
    }
  }

  function retry() {
    errorMessage.value = ''
    const dc = getChannel()
    if (dc) {
      setupChannel(dc)
    } else if (remotePath.value) {
      listDirectory(remotePath.value)
    }
  }

  function navigateUp() {
    // Go to parent directory
    const parts = remotePath.value.split(separator.value).filter(Boolean)
    if (parts.length > 1) {
      parts.pop()
      const parent = separator.value === '\\' 
        ? parts.join('\\')
        : '/' + parts.join('/')
      listDirectory(parent)
    }
  }

  function downloadFile(path) {
    const dc = getChannel()
    if (dc && dc.readyState === 'open') {
      downloadStartTime = Date.now()
      send(dc, { type: 'download', path })
    }
  }

  async function uploadFile(file, destPath) {
    const dc = getChannel()
    if (!dc || dc.readyState !== 'open') return

    activeTransfer.name = file.name
    activeTransfer.direction = 'upload'
    activeTransfer.size = file.size
    activeTransfer.received = 0
    activeTransfer.progress = 0
    downloadStartTime = Date.now()

    // Tell host we're starting an upload
    send(dc, {
      type: 'upload_start',
      name: file.name,
      size: file.size,
      dest: destPath || remotePath.value,
    })

    // Read and send file in chunks
    const reader = new FileReader()
    let offset = 0

    const readNextChunk = () => {
      const slice = file.slice(offset, offset + CHUNK_SIZE)
      reader.readAsArrayBuffer(slice)
    }

    reader.onload = (e) => {
      const chunk = new Uint8Array(e.target.result)
      send(dc, {
        type: 'upload_chunk',
        data: uint8ArrayToBase64(chunk),
        offset: offset,
      })
      offset += chunk.length
      activeTransfer.received = offset
      activeTransfer.progress = Math.min(100, Math.round(offset / file.size * 100))
      updateSpeed()

      if (offset < file.size) {
        readNextChunk()
      } else {
        send(dc, { type: 'upload_end' })
      }
    }

    readNextChunk()
  }

  function createDirectory(path) {
    const dc = getChannel()
    if (dc && dc.readyState === 'open') send(dc, { type: 'mkdir', path })
  }

  function deleteItem(path) {
    const dc = getChannel()
    if (dc && dc.readyState === 'open') send(dc, { type: 'delete', path })
  }

  // ─── Helpers ──────────────────────────────────────────────

  function send(dc, data) {
    if (dc && dc.readyState === 'open') {
      dc.send(JSON.stringify(data))
    }
  }

  function base64ToUint8Array(base64) {
    const binary = atob(base64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i)
    }
    return bytes
  }

  function uint8ArrayToBase64(bytes) {
    let binary = ''
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i])
    }
    return btoa(binary)
  }

  return {
    remotePath: readonly(remotePath),
    remoteEntries: readonly(remoteEntries),
    remotePlatform: readonly(remotePlatform),
    separator: readonly(separator),
    isLoading: readonly(isLoading),
    errorMessage: readonly(errorMessage),
    activeTransfer,
    setupChannel,
    listDirectory,
    retry,
    navigateUp,
    downloadFile,
    uploadFile,
    createDirectory,
    deleteItem,
  }
}
