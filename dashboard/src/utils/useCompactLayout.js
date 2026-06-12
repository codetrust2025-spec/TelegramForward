import { useEffect, useState } from 'react'

const COMPACT_MAX = 1024

export function useCompactLayout(breakpoint = COMPACT_MAX) {
  const [compact, setCompact] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth < breakpoint : false,
  )

  useEffect(() => {
    function onResize() {
      setCompact(window.innerWidth < breakpoint)
    }
    window.addEventListener('resize', onResize)
    onResize()
    return () => window.removeEventListener('resize', onResize)
  }, [breakpoint])

  return compact
}
