const artifacts = [
  {
    artifact_id: 'artifact-001',
    name: 'Engineering Report.docx',
  },
  {
    artifact_id: 'artifact-002',
    name: 'Analysis Results.xlsx',
  },
]

function RecentArtifacts() {
  return (
    <section>
      <h2>Recent Artifacts</h2>

      {artifacts.map((artifact) => (
        <div key={artifact.artifact_id}>
          <p>{artifact.name}</p>
        </div>
      ))}
    </section>
  )
}

export default RecentArtifacts