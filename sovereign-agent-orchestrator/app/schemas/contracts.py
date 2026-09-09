from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class JobStatus(str, Enum):
    queued='queued'; planning='planning'; acting='acting'; observing='observing'; verifying='verifying'; awaiting_approval='awaiting_approval'; delivering='delivering'; failed='failed'; done='done'; cancelled='cancelled'
class PolicyDecision(str, Enum):
    allow='allow'; deny='deny'; require_approval='require_approval'
class UserContext(BaseModel):
    user_id: str='cli-user'; role: str='user'; department: str='general'; clearance: str='internal'; project: str='demo'
class Attachment(BaseModel):
    file_id: str|None=None; name: str|None=None; path: str|None=None; mime_type: str|None=None
class RunOptions(BaseModel):
    max_iterations: int|None=None
class AgentRunRequest(BaseModel):
    task: str=Field(min_length=1); user_context: UserContext=UserContext(); attachments: list[Attachment]=[]; options: RunOptions=RunOptions()
class ApprovalRequest(BaseModel):
    approved: bool; reviewer_user_id: str
class RoutingDecision(BaseModel):
    task_type: str; model_id: str; confidence: float; reason: str; fallback_model_id: str|None=None
    registry_task: str|None=None; model_alias: str|None=None; fallback_alias: str|None=None
class PlanStep(BaseModel):
    step_id: str; description: str; tool: str; tool_args: dict[str,Any]={}; status: str='pending'
class ToolCall(BaseModel):
    call_id: str; tool: str; risk_tier: int; policy_decision: PolicyDecision; success: bool|None=None; result_summary: str|None=None
class Verification(BaseModel):
    passed: bool; checks: dict[str,bool]; notes: list[str]=[]
class Artifact(BaseModel):
    artifact_id: str; name: str; mime_type: str; size_bytes: int; url: str
class Event(BaseModel):
    event_id: str; type: str; status: JobStatus; data: dict[str,Any]={}; timestamp: str
class Job(BaseModel):
    job_id: str; status: JobStatus; task: str; routing: RoutingDecision|None=None; plan: list[PlanStep]=[]; tool_calls: list[ToolCall]=[]; observations: list[dict[str,Any]]=[]; verification: Verification|None=None; requires_human_approval: bool=False; approval: dict[str,Any]|None=None; artifacts: list[Artifact]=[]; final_answer: str|None=None; error: str|None=None
