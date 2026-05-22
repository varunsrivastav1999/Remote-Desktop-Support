/**
 * useScreenShare — Browser-native screen sharing via getDisplayMedia.
 *
 * Uses the same technology as Google Meet / Microsoft Teams:
 *   - getDisplayMedia() API for screen/window/tab capture
 *   - Supports entire screen, specific window, or browser tab
 *   - No Python agent needed — runs entirely in the browser
 *   - Works on all platforms (Mac, Windows, Linux, Chrome OS)
 *
 * This is a FALLBACK mode when the native host agent is not available
 * or when the user wants Meet/Teams-style screen sharing.
 */

import { ref, readonly } from 'vue'

export function useScreenShare() {
  const isSharing = ref(false)
  const localStream = ref(null)
  const shareError = ref('')
  const shareType = ref('') // 'screen' | 'window' | 'tab'

  /**
   * Start sharing the entire screen (like Google Meet / Teams).
   *
   * @param {Object} options - Options for screen sharing
   * @param {boolean} options.audio - Whether to capture system audio
   * @param {string} options.preferDisplay - 'monitor' for full screen, 'window' for app, 'browser' for tab
   * @returns {MediaStream|null} The captured media stream
   */
  async function startScreenShare(options = {}) {
    try {
      shareError.value = ''

      // Check if getDisplayMedia is supported
      if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
        shareError.value = 'Screen sharing is not supported in this browser. Use Chrome, Edge, or Firefox.'
        return null
      }

      // Configure display constraints
      // preferIdealSurface: 'monitor' = entire screen (like Teams)
      const displayMediaOptions = {
        video: {
          displaySurface: options.preferDisplay || 'monitor',
          // Request high quality capture
          width: { ideal: 1920 },
          height: { ideal: 1080 },
          frameRate: { ideal: 30, max: 60 },
          // Cursor always visible in the capture
          cursor: 'always',
        },
        audio: options.audio ? {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        } : false,
        // Chrome 107+ surface switching
        surfaceSwitching: 'include',
        // Show system audio option (Chrome 105+)
        systemAudio: options.audio ? 'include' : 'exclude',
        // Prefer current tab not to be shared (show other screens)
        selfBrowserSurface: 'exclude',
        // Show monitor option first (entire screen)
        monitorTypeSurfaces: 'include',
      }

      console.log('[ScreenShare] Requesting display media...', displayMediaOptions)
      
      // This triggers the browser's native screen picker dialog
      // (same as Google Meet's "Share your screen" dialog)
      const stream = await navigator.mediaDevices.getDisplayMedia(displayMediaOptions)

      if (!stream) {
        shareError.value = 'No screen selected.'
        return null
      }

      localStream.value = stream
      isSharing.value = true

      // Detect what was shared
      const videoTrack = stream.getVideoTracks()[0]
      if (videoTrack) {
        const settings = videoTrack.getSettings()
        shareType.value = settings.displaySurface || 'unknown'
        console.log('[ScreenShare] Sharing started:', {
          displaySurface: settings.displaySurface,
          width: settings.width,
          height: settings.height,
          frameRate: settings.frameRate,
        })

        // Handle user stopping share via browser UI (the "Stop sharing" button)
        videoTrack.onended = () => {
          console.log('[ScreenShare] User stopped sharing via browser UI')
          stopScreenShare()
        }
      }

      return stream

    } catch (err) {
      if (err.name === 'NotAllowedError') {
        shareError.value = 'Screen sharing was denied. Please allow screen access.'
      } else if (err.name === 'NotFoundError') {
        shareError.value = 'No screen available for sharing.'
      } else if (err.name === 'NotReadableError') {
        shareError.value = 'Screen capture failed. Another app may be blocking access.'
      } else {
        shareError.value = `Screen sharing error: ${err.message}`
      }
      console.error('[ScreenShare] Error:', err)
      return null
    }
  }

  /**
   * Stop sharing the screen.
   */
  function stopScreenShare() {
    if (localStream.value) {
      localStream.value.getTracks().forEach(track => track.stop())
      localStream.value = null
    }
    isSharing.value = false
    shareType.value = ''
    shareError.value = ''
    console.log('[ScreenShare] Sharing stopped')
  }

  /**
   * Replace the current share with a new screen/window selection.
   * (Like clicking "Share screen" again in Google Meet)
   */
  async function switchShare(options = {}) {
    stopScreenShare()
    return await startScreenShare(options)
  }

  return {
    isSharing: readonly(isSharing),
    localStream: readonly(localStream),
    shareError: readonly(shareError),
    shareType: readonly(shareType),
    startScreenShare,
    stopScreenShare,
    switchShare,
  }
}
