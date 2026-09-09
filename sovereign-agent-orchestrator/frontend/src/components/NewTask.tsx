import { useState } from 'react'

function NewTask() {
    const [task, setTask] = useState('')
    const [files, setFiles] = useState<File[]>([])
    return (
        <main>
            <h1>New Task</h1>
            <p>Create and run a new agent task.</p>

            <div className="task-form">
                <label htmlFor="task">Task description</label>

                <textarea
                    id="task"
                    value={task}
                    onChange={(event) => setTask(event.target.value)}
                    placeholder="What do you want the agent to do?"
                />

                <label htmlFor="files">Files</label>

                <input
                    id="files"
                    type="file"
                    multiple
                    onChange={(event) => {
                        if (event.target.files) {
                            setFiles(Array.from(event.target.files))
                        }
                    }}
                />

                {files.map((file) => (
                    <p key={file.name}>{file.name}</p>
                ))}

                <button
                    className="new-task-button"
                    onClick={() => {
                        console.log('Task:', task)
                        console.log('Files:', files)
                    }}
                >
                    Run Task
                </button>
            </div>
        </main>
    )
}

export default NewTask