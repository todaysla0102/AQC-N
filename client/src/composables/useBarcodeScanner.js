import { BrowserMultiFormatReader } from '@zxing/browser'
import { BarcodeFormat, DecodeHintType, NotFoundException } from '@zxing/library'
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'

const BARCODE_HINTS = new Map([
  [DecodeHintType.POSSIBLE_FORMATS, [
    BarcodeFormat.CODE_128,
    BarcodeFormat.CODE_39,
    BarcodeFormat.CODE_93,
    BarcodeFormat.CODABAR,
    BarcodeFormat.EAN_13,
    BarcodeFormat.EAN_8,
    BarcodeFormat.UPC_A,
    BarcodeFormat.UPC_E,
    BarcodeFormat.ITF,
  ]],
  [DecodeHintType.TRY_HARDER, true],
])

function buildScannerHints(formats) {
  const nextFormats = Array.isArray(formats) && formats.length ? formats : BARCODE_HINTS.get(DecodeHintType.POSSIBLE_FORMATS)
  return new Map([
    [DecodeHintType.POSSIBLE_FORMATS, nextFormats],
    [DecodeHintType.TRY_HARDER, true],
  ])
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function supportsCameraScan() {
  return window.isSecureContext !== false && !!navigator.mediaDevices?.getUserMedia
}


export function useBarcodeScanner({ onDetected, formats } = {}) {
  const videoRef = ref(null)
  const scanning = ref(false)
  const scannerPending = ref(false)
  const scannerError = ref('')
  const scannerManualFocusSupported = ref(false)
  const scannerFocusMessage = ref('')

  let codeReader = null
  let scannerControls = null
  let lastDetectedCode = ''
  let lastDetectedAt = 0
  let scannerFocusMessageTimer = null

  const scannerHint = computed(() => {
    if (scanning.value) {
      if (scannerFocusMessage.value) {
        return scannerFocusMessage.value
      }
      if (scannerManualFocusSupported.value) {
        return '摄像头已开启，点击画面可手动对焦，识别到条码后会自动回填。'
      }
      return '摄像头已开启，请尽量让条码靠近画面中央并保持稳定。'
    }
    if (scannerPending.value) {
      return '正在请求摄像头权限并准备扫码画面，请稍候。'
    }
    if (!window.isSecureContext) {
      return '当前环境不是安全上下文，摄像头扫码可能不可用；可改用扫码枪或手动输入。'
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      return '当前浏览器无法调用摄像头，可改用扫码枪或手动输入。'
    }
    if (scannerError.value) {
      return scannerError.value
    }
    return '支持移动端和 Safari 摄像头扫码，也支持扫码枪直接输入。'
  })

  function clearFocusMessageTimer() {
    if (scannerFocusMessageTimer) {
      window.clearTimeout(scannerFocusMessageTimer)
      scannerFocusMessageTimer = null
    }
  }

  function setScannerFocusMessage(message = '', duration = 1800) {
    clearFocusMessageTimer()
    scannerFocusMessage.value = message
    if (!message) {
      return
    }
    scannerFocusMessageTimer = window.setTimeout(() => {
      scannerFocusMessage.value = ''
      scannerFocusMessageTimer = null
    }, duration)
  }

  function getActiveVideoTrack() {
    const stream = videoRef.value?.srcObject
    if (!stream?.getVideoTracks) {
      return null
    }
    return stream.getVideoTracks()[0] || null
  }

  async function applyTrackConstraints(constraints) {
    const track = getActiveVideoTrack()
    if (!track?.applyConstraints) {
      return false
    }
    try {
      await track.applyConstraints(constraints)
      return true
    } catch (error) {
      console.warn('Failed to apply camera constraints', error)
      return false
    }
  }

  async function primeScannerFocus() {
    const track = getActiveVideoTrack()
    const capabilities = track?.getCapabilities?.() || {}
    const focusModes = Array.isArray(capabilities.focusMode) ? capabilities.focusMode : []

    scannerManualFocusSupported.value = Boolean(
      focusModes.includes('single-shot')
      || focusModes.includes('manual')
      || capabilities.pointsOfInterest
      || capabilities.focusDistance,
    )

    const advanced = []
    if (focusModes.includes('continuous')) {
      advanced.push({ focusMode: 'continuous' })
    } else if (focusModes.includes('single-shot')) {
      advanced.push({ focusMode: 'single-shot' })
    }

    if (capabilities.zoom && Number.isFinite(capabilities.zoom.max) && capabilities.zoom.max > 1) {
      const minZoom = Number.isFinite(capabilities.zoom.min) ? capabilities.zoom.min : 1
      advanced.push({ zoom: clamp(1.15, minZoom, capabilities.zoom.max) })
    }

    if (advanced.length) {
      await applyTrackConstraints({ advanced })
    }
  }

  async function focusScannerAt(event) {
    if (!scanning.value) {
      return false
    }
    const track = getActiveVideoTrack()
    const capabilities = track?.getCapabilities?.() || {}
    const focusModes = Array.isArray(capabilities.focusMode) ? capabilities.focusMode : []
    const advanced = []

    if (event?.currentTarget?.getBoundingClientRect) {
      const rect = event.currentTarget.getBoundingClientRect()
      const pointSource = event.touches?.[0] || event.changedTouches?.[0] || event
      if (rect.width > 0 && rect.height > 0 && pointSource) {
        const x = clamp((pointSource.clientX - rect.left) / rect.width, 0.08, 0.92)
        const y = clamp((pointSource.clientY - rect.top) / rect.height, 0.08, 0.92)
        if (capabilities.pointsOfInterest) {
          advanced.push({ pointsOfInterest: [{ x, y }] })
        }
      }
    }

    if (focusModes.includes('single-shot')) {
      advanced.push({ focusMode: 'single-shot' })
    } else if (focusModes.includes('manual') && capabilities.focusDistance) {
      const focusDistance = Number.isFinite(capabilities.focusDistance.max)
        ? capabilities.focusDistance.max
        : Number.isFinite(capabilities.focusDistance.min)
          ? capabilities.focusDistance.min
          : undefined
      if (focusDistance !== undefined) {
        advanced.push({ focusMode: 'manual', focusDistance })
      }
    } else if (focusModes.includes('continuous')) {
      advanced.push({ focusMode: 'continuous' })
    }

    if (!advanced.length) {
      return false
    }

    const applied = await applyTrackConstraints({ advanced })
    if (applied) {
      setScannerFocusMessage('已触发手动对焦，请将条码保持在取景框中央。')
      if (focusModes.includes('single-shot') && focusModes.includes('continuous')) {
        window.setTimeout(() => {
          void applyTrackConstraints({ advanced: [{ focusMode: 'continuous' }] })
        }, 260)
      }
    }
    return applied
  }

  async function stopScanner({ keepPending = false } = {}) {
    scanning.value = false
    if (!keepPending) {
      scannerPending.value = false
    }
    lastDetectedCode = ''
    lastDetectedAt = 0
    scannerManualFocusSupported.value = false
    setScannerFocusMessage('')

    const currentControls = scannerControls
    scannerControls = null
    try {
      currentControls?.stop?.()
    } catch (error) {
      console.error(error)
    }

    if (codeReader) {
      try {
        codeReader.reset()
      } catch (error) {
        console.error(error)
      }
      codeReader = null
    }

    if (videoRef.value) {
      try {
        videoRef.value.pause()
      } catch (error) {
        console.error(error)
      }
      videoRef.value.srcObject = null
    }
  }

  async function startScanner() {
    if (!supportsCameraScan()) {
      scannerError.value = '当前浏览器环境不支持摄像头扫码，请改用扫码枪或手动输入'
      return false
    }

    scannerPending.value = true
    await nextTick()
    await new Promise((resolve) => window.requestAnimationFrame(resolve))

    if (!videoRef.value) {
      scannerPending.value = false
      scannerError.value = '扫码画面尚未就绪，请稍后重试'
      return false
    }

    await stopScanner({ keepPending: true })
    scannerError.value = ''
    codeReader = new BrowserMultiFormatReader(buildScannerHints(formats), {
      delayBetweenScanAttempts: 90,
      delayBetweenScanSuccess: 360,
      tryPlayVideoTimeout: 2600,
    })
    const handleDecodeResult = async (result, error) => {
      if (result) {
        const rawText = String(result.getText?.() || result.text || '').trim()
        if (!rawText) {
          return
        }

        const now = Date.now()
        if (rawText === lastDetectedCode && now - lastDetectedAt < 1200) {
          return
        }

        lastDetectedCode = rawText
        lastDetectedAt = now
        await stopScanner()
        await Promise.resolve(onDetected?.(rawText))
        return
      }

      if (error && !(error instanceof NotFoundException) && error?.name !== 'NotFoundException') {
        scannerError.value = '扫码识别中断，请重新打开摄像头后再试'
      }
    }

    try {
      videoRef.value.setAttribute('playsinline', 'true')
      videoRef.value.muted = true

      try {
        scannerControls = await codeReader.decodeFromConstraints(
          {
            audio: false,
            video: {
              facingMode: { ideal: 'environment' },
              width: { ideal: 1280, min: 640 },
              height: { ideal: 720, min: 480 },
            },
          },
          videoRef.value,
          handleDecodeResult,
        )
      } catch (constraintError) {
        console.warn('decodeFromConstraints failed, falling back to default device', constraintError)
        scannerControls = await codeReader.decodeFromVideoDevice(undefined, videoRef.value, handleDecodeResult)
      }

      await primeScannerFocus()
      scanning.value = true
      scannerPending.value = false
      return true
    } catch (error) {
      console.error(error)
      await stopScanner()
      if (error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError') {
        scannerError.value = '浏览器尚未授予摄像头权限，请允许访问后重试'
      } else if (error?.name === 'NotFoundError' || error?.name === 'DevicesNotFoundError') {
        scannerError.value = '当前设备未找到可用摄像头，请改用扫码枪或手动输入'
      } else {
        scannerError.value = '摄像头启动失败，请检查浏览器权限或改用手动输入'
      }
      return false
    }
  }

  async function toggleScanner() {
    if (scanning.value || scannerPending.value) {
      await stopScanner()
      return
    }
    await startScanner()
  }

  onBeforeUnmount(() => {
    clearFocusMessageTimer()
    void stopScanner()
  })

  return {
    videoRef,
    scanning,
    scannerPending,
    scannerHint,
    scannerError,
    scannerManualFocusSupported,
    startScanner,
    stopScanner,
    toggleScanner,
    focusScannerAt,
  }
}
