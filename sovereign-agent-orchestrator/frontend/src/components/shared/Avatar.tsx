// Deterministic initials avatar. No remote gravatar/photo fetch -- this product
// ships air-gapped, so an <img> to an external host would simply render broken.
// Hue is derived from the name so a given operator keeps the same color.
function hueFor(seed: string) {
  let hash = 0
  for (let index = 0; index < seed.length; index += 1) hash = (hash * 31 + seed.charCodeAt(index)) % 360
  return hash
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase() ?? '').join('')
}

function Avatar({ name, size = 34 }: { name: string; size?: number }) {
  const hue = hueFor(name)
  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-lg font-semibold text-white/90"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.36,
        background: `linear-gradient(140deg, hsl(${hue} 38% 42%), hsl(${(hue + 48) % 360} 34% 28%))`,
      }}
      aria-hidden
    >
      {initials(name)}
    </div>
  )
}

export default Avatar
