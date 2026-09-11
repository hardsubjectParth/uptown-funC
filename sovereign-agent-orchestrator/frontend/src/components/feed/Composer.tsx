import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { PaperclipIcon, ArrowUpIcon } from '../shell/icons'

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
    <div className="mx-auto w-full max-w-[860px]">
      <form
        onSubmit={handleSubmit}
        className={`flex items-end gap-2 rounded-2xl border bg-surface px-5 py-3 transition-colors ${
          focused ? 'border-accent/45 shadow-[0_0_22px_rgba(143,184,156,0.1)]' : 'border-white/8'
        }`}
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
          className="max-h-40 flex-1 resize-none bg-transparent py-2.5 text-[14.5px] text-foreground outline-none placeholder:text-muted-foreground"
        />

        <label
          className="flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-lg text-muted-foreground transition hover:bg-white/5 hover:text-foreground"
          title="Attach a file"
        >
          <PaperclipIcon size={18} />
          <input type="file" multiple hidden onChange={(event) => setFiles(Array.from(event.target.files ?? []))} />
        </label>

        <button
          type="submit"
          disabled={submitting || !task.trim()}
          aria-label="Send instruction"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground transition hover:bg-primary-hover disabled:opacity-35"
        >
          <ArrowUpIcon size={18} />
        </button>
      </form>

      {files.length > 0 ? (
        <div className="mt-2.5 flex flex-wrap gap-2">
          {files.map((file) => (
            <span key={`${file.name}-${file.size}`} className="border-hairline rounded-lg px-2.5 py-1 text-xs text-muted-foreground">
              {file.name}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export default Composer
