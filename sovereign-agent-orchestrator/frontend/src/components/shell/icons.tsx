// Minimal dependency-free line icons -- no icon library added just for a handful
// of glyphs. All share one stroke spec so they read as a single set, and all take
// `size` because the nav (16px), inline affordances (14px) and the colored task
// tiles (18px) draw from the same file.
type IconProps = { className?: string; size?: number }

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

function Svg({ className, size = 16, children }: IconProps & { children: React.ReactNode }) {
  return <svg viewBox="0 0 20 20" width={size} height={size} className={className} aria-hidden {...base}>{children}</svg>
}

/* ---------------------------------------------------------------- navigation */

export function FeedIcon(props: IconProps) {
  // Terminal prompt ">_", per the mockup's Intelligence Feed glyph.
  return <Svg {...props}><path d="M4 6l3.5 4L4 14" /><path d="M11 14.5h5" /></Svg>
}

export function KnowledgeIcon(props: IconProps) {
  return <Svg {...props}><path d="M3 5a2 2 0 0 1 2-2h4v14H5a2 2 0 0 1-2-2z" /><path d="M17 5a2 2 0 0 0-2-2h-4v14h4a2 2 0 0 0 2-2z" /></Svg>
}

export function TasksIcon(props: IconProps) {
  // Checklist: two ticks with rules beside them.
  return <Svg {...props}><path d="M3 6l1.5 1.5L7.5 4.5" /><path d="M3 13.5L4.5 15l3-3" /><path d="M10.5 6H17" /><path d="M10.5 13.5H17" /></Svg>
}

export function ArtifactsIcon(props: IconProps) {
  // Archive box: lid over a body with a pull slot.
  return <Svg {...props}><rect x="3" y="3.5" width="14" height="3.5" rx="1" /><path d="M4.5 7v8a1.5 1.5 0 0 0 1.5 1.5h8a1.5 1.5 0 0 0 1.5-1.5V7" /><path d="M8.5 10.5h3" /></Svg>
}

/* -------------------------------------------------------------- affordances */

export function SearchIcon(props: IconProps) {
  return <Svg {...props}><circle cx="9" cy="9" r="5" /><path d="M12.8 12.8L16.5 16.5" /></Svg>
}

export function ChatIcon(props: IconProps) {
  return <Svg {...props}><path d="M3.5 5.5a1.5 1.5 0 0 1 1.5-1.5h10a1.5 1.5 0 0 1 1.5 1.5v6a1.5 1.5 0 0 1-1.5 1.5H8l-4.5 3z" /></Svg>
}

export function ShareIcon(props: IconProps) {
  return <Svg {...props}><circle cx="15" cy="5" r="2" /><circle cx="5" cy="10" r="2" /><circle cx="15" cy="15" r="2" /><path d="M6.8 9l6.4-3.2M6.8 11l6.4 3.2" /></Svg>
}

export function StarIcon(props: IconProps) {
  return <Svg {...props}><path d="M10 3l2.1 4.4 4.7.6-3.4 3.3.9 4.7-4.3-2.3-4.3 2.3.9-4.7L3.2 8l4.7-.6z" /></Svg>
}

export function KebabIcon(props: IconProps) {
  return <Svg {...props}><circle cx="10" cy="4.5" r="1" /><circle cx="10" cy="10" r="1" /><circle cx="10" cy="15.5" r="1" /></Svg>
}

export function PaperclipIcon(props: IconProps) {
  return <Svg {...props}><path d="M14.5 9.5l-4.8 4.8a3 3 0 0 1-4.2-4.2l5.5-5.5a2 2 0 0 1 2.8 2.8l-5.5 5.5a1 1 0 0 1-1.4-1.4l4.8-4.8" /></Svg>
}

export function ArrowUpIcon(props: IconProps) {
  return <Svg {...props}><path d="M10 16V4" /><path d="M5.5 8.5L10 4l4.5 4.5" /></Svg>
}

export function ChevronRightIcon(props: IconProps) {
  return <Svg {...props}><path d="M8 5l5 5-5 5" /></Svg>
}

export function ChevronDownIcon(props: IconProps) {
  return <Svg {...props}><path d="M5 8l5 5 5-5" /></Svg>
}

export function UploadCloudIcon(props: IconProps) {
  return <Svg {...props}><path d="M5.5 14a3.5 3.5 0 0 1-.4-7A4.5 4.5 0 0 1 14 7.2a3 3 0 0 1 .5 6.8" /><path d="M10 16V8.5" /><path d="M7.5 11L10 8.5l2.5 2.5" /></Svg>
}

export function DownloadIcon(props: IconProps) {
  return <Svg {...props}><path d="M10 3v9" /><path d="M6 8.5l4 4 4-4" /><path d="M4 16h12" /></Svg>
}

/* ------------------------------------------------------- scope / status tiles */

export function ShieldIcon(props: IconProps) {
  return <Svg {...props}><path d="M10 3l5.5 2v5c0 3.2-2.3 5.6-5.5 7-3.2-1.4-5.5-3.8-5.5-7V5z" /></Svg>
}

export function UserIcon(props: IconProps) {
  return <Svg {...props}><circle cx="10" cy="7" r="2.8" /><path d="M4.5 16.5a5.5 5.5 0 0 1 11 0" /></Svg>
}

export function UsersIcon(props: IconProps) {
  return <Svg {...props}><circle cx="8" cy="7" r="2.5" /><path d="M3 16a5 5 0 0 1 10 0" /><path d="M13.5 5.2a2.5 2.5 0 0 1 0 4.6" /><path d="M14.5 11.4A5 5 0 0 1 17.5 16" /></Svg>
}

export function ChipIcon(props: IconProps) {
  return <Svg {...props}><rect x="5.5" y="5.5" width="9" height="9" rx="1.5" /><rect x="8.5" y="8.5" width="3" height="3" /><path d="M8 5.5V3M12 5.5V3M8 17v-2.5M12 17v-2.5M5.5 8H3M5.5 12H3M17 8h-2.5M17 12h-2.5" /></Svg>
}

export function DatabaseIcon(props: IconProps) {
  return <Svg {...props}><ellipse cx="10" cy="5.5" rx="5.5" ry="2.5" /><path d="M4.5 5.5v9c0 1.4 2.5 2.5 5.5 2.5s5.5-1.1 5.5-2.5v-9" /><path d="M4.5 10c0 1.4 2.5 2.5 5.5 2.5s5.5-1.1 5.5-2.5" /></Svg>
}

export function AlertIcon(props: IconProps) {
  return <Svg {...props}><circle cx="10" cy="10" r="7" /><path d="M10 6.5v4.5" /><path d="M10 13.5v.01" /></Svg>
}

export function ChartIcon(props: IconProps) {
  return <Svg {...props}><path d="M3.5 13.5l4-4 3 3 6-6" /><path d="M13 6.5h3.5V10" /></Svg>
}

export function TableIcon(props: IconProps) {
  return <Svg {...props}><rect x="3" y="4.5" width="14" height="11" rx="1.5" /><path d="M3 8.5h14M8 8.5v7" /></Svg>
}

export function FileIcon(props: IconProps) {
  return <Svg {...props}><path d="M6 2.5h5L15 6.5v11H6z" /><path d="M11 2.5v4h4" /></Svg>
}

export function CheckIcon(props: IconProps) {
  return <Svg {...props}><path d="M4.5 10.5l3.5 3.5 7.5-8" /></Svg>
}

export function XIcon(props: IconProps) {
  return <Svg {...props}><path d="M6 6l8 8M14 6l-8 8" /></Svg>
}
