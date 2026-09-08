from dataclasses import dataclass
from enum import Enum
class Decision(str,Enum): ALLOW='allow'; DENY='deny'; REQUIRE_APPROVAL='require_approval'
@dataclass
class PolicyResult: decision: Decision; reason: str
class Policy:
    risks={'search_documents':0,'read_file':0,'write_file':1,'generate_docx':1,'run_python':1,'ocr_document':0,'describe_image':0}
    def check(self,tool,user):
        if tool not in self.risks:return PolicyResult(Decision.DENY,'TOOL_NOT_REGISTERED')
        risk=self.risks[tool]
        if risk>=2:return PolicyResult(Decision.REQUIRE_APPROVAL,'RISK_TIER_REQUIRES_REVIEW')
        if tool=='generate_docx': return PolicyResult(Decision.REQUIRE_APPROVAL,'DOCUMENT_ARTIFACT_REQUIRES_REVIEW') if user.get('role')=='approver_demo' else PolicyResult(Decision.ALLOW,'LOW_RISK_CONFIGURED')
        return PolicyResult(Decision.ALLOW,'LOW_RISK_CONFIGURED')
