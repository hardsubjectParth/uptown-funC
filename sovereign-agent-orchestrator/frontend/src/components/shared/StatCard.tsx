import { useEffect, useState } from 'react'

// Counts up from 0 to `value` over 500ms on mount/value-change. Numeric values only --
// pass a string (e.g. "99.4%") to skip the animation and render it as-is.
function useCountUp(value: number, durationMs = 500) {
  const [display, setDisplay] = useState(0)
  useEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      setDisplay(value)
      return
    }
    let frame: number
    const start = performance.now()
    function tick(now: number) {
      const progress = Math.min((now - start) / durationMs, 1)
      const eased = 1 - (1 - progress) ** 3
      setDisplay(Math.round(value * eased))
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [value, durationMs])
  return display
}

type StatCardProps = { label: string; value: number | string; accent?: boolean; suffix?: string }

function StatCard({ label, value, accent = false, suffix = '' }: StatCardProps) {
  const isNumeric = typeof value === 'number'
  const animated = useCountUp(isNumeric ? value : 0)
  return (
    <div className="border-hairline bg-surface px-4 py-4">
      <p className={`stat-number text-2xl font-semibold ${accent ? 'text-accent' : 'text-foreground'}`}>
        {isNumeric ? animated : value}{suffix}
      </p>
      <p className="label-micro mt-1.5">{label}</p>
    </div>
  )
}

export default StatCard
