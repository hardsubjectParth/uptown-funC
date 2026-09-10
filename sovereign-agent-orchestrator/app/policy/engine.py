from dataclasses import dataclass
from enum import Enum
class Decision(str,Enum): ALLOW='allow'; DENY='deny'; REQUIRE_APPROVAL='require_approval'
@dataclass
class PolicyResult: decision: Decision; reason: str
class Policy:
    risks={'search_documents':0,'read_file':0,'write_file':1,'generate_docx':1,'ingest_document':0,'list_sources':0,'export_report':1,'spreadsheet_profile':0,'redact_pii':1,'extract_tables':0,'ocr_document':0,'search_db':1,'send_email':2,'create_calendar_event':2,'run_python':1,'describe_image':0}
    def check(self,tool,user):
        if tool not in self.risks:return PolicyResult(Decision.DENY,'TOOL_NOT_REGISTERED')
        risk=self.risks[tool]
        if risk>=2:return PolicyResult(Decision.REQUIRE_APPROVAL,'RISK_TIER_REQUIRES_REVIEW')
        if tool=='generate_docx': return PolicyResult(Decision.REQUIRE_APPROVAL,'DOCUMENT_ARTIFACT_REQUIRES_REVIEW') if user.get('role')=='approver_demo' else PolicyResult(Decision.ALLOW,'LOW_RISK_CONFIGURED')
        return PolicyResult(Decision.ALLOW,'LOW_RISK_CONFIGURED')
