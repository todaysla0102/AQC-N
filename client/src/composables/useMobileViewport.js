import { onBeforeUnmount, onMounted, ref } from 'vue'


export function useMobileViewport(breakpoint = 980) {
  const isMobileViewport = ref(false)

  function updateViewport() {
    if (typeof window === 'undefined') {
      isMobileViewport.value = false
      return
    }
    isMobileViewport.value = window.innerWidth <= breakpoint
  }

  onMounted(() => {
    updateViewport()
    window.addEventListener('resize', updateViewport, { passive: true })
  })

  onBeforeUnmount(() => {
    if (typeof window === 'undefined') {
      return
    }
    window.removeEventListener('resize', updateViewport)
  })

  return {
    isMobileViewport,
    updateViewport,
  }
}
