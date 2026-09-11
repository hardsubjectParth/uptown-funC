import type { Tier } from '../../types/api'

// Tier is a security-relevant fact, so it stays literal and always visible. It is
// rendered as a neutral outlined chip rather than a colored pill on purpose --
// coloring tiers would imply a ranking the palette doesn't actually encode, and
// would collide with the status pills that DO use color meaningfully.
function TierLabel({ tier }: { tier: Tier | string }) {
  return (
    <span className="inline-flex shrink-0 items-center rounded-md border border-white/12 bg-white/5 px-1.5 py-0.5 text-[10px] font-semibold tracking-[0.1em] text-foreground/70 uppercase">
      {String(tier)}
    </span>
  )
}

export default TierLabel
