import type { ReactNode } from 'react'

// The rounded, tinted glyph tile that fronts a task row, a document card or an
// artifact preview. One tone token drives fill, hairline and glyph together so a
// tile can never end up with, say, an amber icon on a blue ground.
export type Tone = 'info' | 'success' | 'warning' | 'danger' | 'accent' | 'neutral'

const TONE: Record<Tone, { color: string; bg: string; border: string }> = {
  info: { color: 'var(--color-info)', bg: 'rgba(110,155,240,0.12)', border: 'rgba(110,155,240,0.28)' },
  success: { color: 'var(--color-success)', bg: 'rgba(111,207,151,0.12)', border: 'rgba(111,207,151,0.28)' },
  warning: { color: 'var(--color-warning)', bg: 'rgba(227,179,65,0.12)', border: 'rgba(227,179,65,0.28)' },
  danger: { color: 'var(--color-danger)', bg: 'rgba(212,106,106,0.12)', border: 'rgba(212,106,106,0.28)' },
  accent: { color: 'var(--color-accent)', bg: 'rgba(143,184,156,0.12)', border: 'rgba(143,184,156,0.26)' },
  neutral: { color: 'var(--color-muted-foreground)', bg: 'rgba(255,255,255,0.04)', border: 'rgba(255,255,255,0.08)' },
}

type IconTileProps = { tone?: Tone; size?: number; className?: string; children: ReactNode }

function IconTile({ tone = 'neutral', size = 40, className = '', children }: IconTileProps) {
  const palette = TONE[tone]
  return (
    <div
      className={`flex shrink-0 items-center justify-center rounded-xl border ${className}`}
      style={{ width: size, height: size, color: palette.color, background: palette.bg, borderColor: palette.border }}
    >
      {children}
    </div>
  )
}

export default IconTile
export { TONE }
