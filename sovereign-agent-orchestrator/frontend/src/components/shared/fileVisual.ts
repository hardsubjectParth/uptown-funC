import { FileIcon, TableIcon, ChartIcon } from '../shell/icons'
import type { Tone } from './IconTile'

// Extension drives the tile, not mime_type: mime is whatever the browser reported
// at upload time and is very often a generic octet-stream.
export function fileVisual(name: string): { Icon: typeof FileIcon; tone: Tone; tag: string } {
  const extension = (name.split('.').pop() ?? '').toLowerCase()
  if (extension === 'csv' || extension === 'xlsx' || extension === 'xlsm') return { Icon: TableIcon, tone: 'success', tag: extension }
  if (extension === 'pptx' || extension === 'ppt') return { Icon: ChartIcon, tone: 'warning', tag: extension }
  if (extension === 'pdf') return { Icon: ChartIcon, tone: 'danger', tag: 'pdf' }
  if (extension === 'docx' || extension === 'doc') return { Icon: FileIcon, tone: 'info', tag: extension }
  if (extension === 'py' || extension === 'js' || extension === 'ts' || extension === 'sh') return { Icon: FileIcon, tone: 'accent', tag: extension }
  return { Icon: FileIcon, tone: 'neutral', tag: extension || 'file' }
}

export function formatSize(bytes?: number) {
  if (!bytes || bytes <= 0) return 'Unknown size'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function relativeTime(iso?: string) {
  if (!iso) return 'unknown'
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.round(diffMs / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}
