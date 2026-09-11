import { useRef, useState } from 'react'
import type { FormEvent } from 'react'

type ComposerProps = {
  onSubmit: (task: string, files: File[]) => void
  submitting: boolean
}

function Composer({ onSubmit, submitting }: ComposerProps) {
  const [task, setTask] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [focused, setFocused] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function grow() {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!task.trim() || submitting) return
    onSubmit(task.trim(), files)
    setTask('')
    setFiles([])
    requestAnimationFrame(grow)
  }

  return (
    <div className="border-t border-white/8 px-6 py-4">
      <form
        onSubmit={handleSubmit}
        className={`border-hairline flex items-end gap-2 bg-surface px-3 py-2 transition-colors ${focused ? 'border-accent shadow-[0_0_0_1px_var(--color-accent),0_0_14px_rgba(76,141,255,0.25)]' : ''}`}
      >
        <textarea
          ref={textareaRef}
          rows={1}
          value={task}
          onChange={(event) => { setTask(event.target.value); grow() }}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault()
              event.currentTarget.form?.requestSubmit()
            }
          }}
          placeholder="Instruct Sovereign Intelligence..."
          className="max-h-40 flex-1 resize-none bg-transparent py-1.5 font-mono text-sm text-foreground outline-none placeholder:text-muted-foreground"
        />

        <label className="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center text-muted-foreground hover:text-foreground" title="Attach a file">
          +
          <input type="file" multiple hidden onChange={(event) => setFiles(Array.from(event.target.files ?? []))} />
        </label>

        <button
          type="submit"
          disabled={submitting || !task.trim()}
          className="flex h-8 w-8 shrink-0 items-center justify-center bg-accent text-accent-foreground transition disabled:opacity-40"
        >
          {submitting ? '…' : '↑'}
        </button>
      </form>

      {files.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {files.map((file) => <span key={`${file.name}-${file.size}`} className="border-hairline px-2 py-1 text-xs text-muted-foreground">{file.name}</span>)}
        </div>
      ) : null}
    </div>
  )
}

export default Composer
