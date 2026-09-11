import type { Tier } from '../../types/api'

// Text-weight only, never a colored pill -- tier is a security-relevant fact the
// spec explicitly asks to keep visible, not decorate away.
function TierLabel({ tier }: { tier: Tier | string }) {
  return <span className="label-micro font-semibold text-foreground/70">{String(tier).toUpperCase()}</span>
}

export default TierLabel
