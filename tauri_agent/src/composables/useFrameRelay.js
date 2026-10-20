/**
 * Screen relay over the signaling WebSocket.
 *
 * WebRTC needs a network path between the two machines (direct, or through a TURN relay).
 * When there is none, the controller waits forever on "Stream established". The signaling
 * socket always works (it is how the page reached the server), so as a fallback the host
 * sends its screen as JPEG frames over it. Slower than WebRTC, but it works on any network.
 */

const MAX_WIDTH = 1280
const FRAME_INTERVAL_MS = 200 // ~5 fps
const JPEG_QUALITY = 0.6
// Skip a frame while this much is still queued on the socket, so a slow link never builds a backlog
const MAX_BUFFERED_BYTES = 512 * 1024

/**
 * Timer that keeps firing in a background tab (page timers there are throttled to 1/s or less,
 * and the host's tab is usually not the one in front while sharing).
 */
function createTicker(intervalMs, onTick) {
  try {
    const source = `setInterval(() => postMessage(0), ${intervalMs})`
    const url = URL.createObjectURL(new Blob([source], { type: 'text/javascript' }))
    const worker = new Worker(url)
    URL.revokeObjectURL(url)
    worker.onmessage = onTick
    return () => worker.terminate()
  } catch (_) {
    const timer = setInterval(onTick, intervalMs)
    return () => clearInterval(timer)
  }
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '')
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}

/**
 * Host side: capture `stream` and hand frames to `send` ({type: 'frame', w, h, data}).
 * `bufferedAmount()` reports how many bytes the socket still has queued.
 */
export function createFrameSender(stream, send, bufferedAmount = () => 0) {
  const video = document.createElement('video')
  video.muted = true
  video.playsInline = true
  video.srcObject = stream
  video.play().catch(() => {})

  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d')
  let busy = false

  const stopTicker = createTicker(FRAME_INTERVAL_MS, async () => {
    if (busy || !video.videoWidth || bufferedAmount() > MAX_BUFFERED_BYTES) return
    busy = true
    try {
      const scale = Math.min(1, MAX_WIDTH / video.videoWidth)
      const width = Math.round(video.videoWidth * scale)
      const height = Math.round(video.videoHeight * scale)
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width
        canvas.height = height
      }
      context.drawImage(video, 0, 0, width, height)
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY))
      if (blob) send({ type: 'frame', w: width, h: height, data: await blobToBase64(blob) })
    } catch (err) {
      console.warn('[FrameRelay] Could not send frame:', err)
    } finally {
      busy = false
    }
  })

  return function stop() {
    stopTicker()
    video.srcObject = null
  }
}

/**
 * Controller side: draws received frames onto a canvas and exposes it as a MediaStream, so the
 * normal remote-screen video element shows it unchanged.
 */
export function createFrameReceiver() {
  const canvas = document.createElement('canvas')
  canvas.width = 1280
  canvas.height = 720
  const context = canvas.getContext('2d')
  const stream = canvas.captureStream(15)
  let drawing = false

  async function push(message) {
    if (drawing || !message?.data) return
    drawing = true
    try {
      const bytes = Uint8Array.from(atob(message.data), c => c.charCodeAt(0))
      const bitmap = await createImageBitmap(new Blob([bytes], { type: 'image/jpeg' }))
      if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
        canvas.width = bitmap.width
        canvas.height = bitmap.height
      }
      context.drawImage(bitmap, 0, 0)
      bitmap.close()
    } catch (err) {
      console.warn('[FrameRelay] Could not draw frame:', err)
    } finally {
      drawing = false
    }
  }

  function stop() {
    for (const track of stream.getTracks()) track.stop()
  }

  return { stream, push, stop }
}
