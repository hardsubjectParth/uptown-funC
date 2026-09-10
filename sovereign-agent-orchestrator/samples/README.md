# Sample documents

Small fixtures for exercising the pipeline without needing real data. Nothing
here is confidential; they were written for testing.

| file | purpose |
|---|---|
| `inspection-2026-03.md` | A clean fire-safety inspection report. Two non-compliant findings (FE-114 overdue + failed pressure check, exit E-2 obstructed) and two compliant ones, with the applicable SOP text. Use it for summarization and approval-note tasks. |
| `poisoned-sop.md` | **Contains a deliberate prompt-injection attack.** It instructs the model to approve everything regardless of findings and to hide the instruction. Used to verify the guardrail in `app/guard/injection.py`. Index it alongside the clean report and confirm the job reports `injection_findings` and the artifact carries a security warning. |
| `retrieval/` | A four-document corpus where embedding similarity alone ranks the wrong document first. Ask *"which extinguisher is overdue for service"*: embeddings put `training.md` on top, the cross-encoder reranker correctly promotes `extinguisher.md`. Used to demonstrate why reranking is enabled. |

## Quick use

```bash
# index them
python - <<'PY'
import asyncio, glob
from app.rag.service import RagService
rag = RagService('sqlite:///./demo.db', 'http://localhost:8080/v1', 'embedder', 'vision')
for f in glob.glob('samples/*.md'):
    print(asyncio.run(rag.ingest(f, {'tenant_id': 'default', 'clearance': 'internal'})))
PY

# ask something
MODEL_MODE=llamaswap LLM_BASE_URL=http://localhost:8080/v1 \
DATABASE_URL=sqlite:///./demo.db WORKSPACE_ROOT=./workspace \
python cli.py "Summarize the FE-114 findings and state whether it is compliant."
```
