const tasks = [
  {
    job_id: 'job-001',
    task: 'Analyze engineering report',
    status: 'done',
  },
  {
    job_id: 'job-002',
    task: 'Search knowledge base',
    status: 'acting',
  },
]

function RecentTasks() {
  return (
    <section>
      <h2>Recent Tasks</h2>

      {tasks.map((task) => (
        <div className="task-card" key={task.job_id}>
          <h3>{task.task}</h3>
          <p>
            Status:{' '}
            <span className={`status ${task.status}`}>
              {task.status}
            </span>
          </p>
        </div>
      ))}
    </section>
  )
}

export default RecentTasks