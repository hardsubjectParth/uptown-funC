from dataclasses import dataclass
from enum import Enum
class Decision(str,Enum): ALLOW='allow'; DENY='deny'; REQUIRE_APPROVAL='require_approval'
@dataclass
class PolicyResult: decision: Decision; reason: str
class Policy:
    risks={'search_documents':0,'read_file':0,'write_file':1,'generate_docx':1,'generate_xlsx':1,'generate_pptx':1,'generate_pdf':1,'ingest_document':0,'list_sources':0,'export_report':1,'spreadsheet_profile':0,'redact_pii':1,'extract_tables':0,'ocr_document':0,'search_db':1,'send_email':2,'create_calendar_event':2,'run_python':1,'describe_image':0}
    # Sandboxed code execution runs with no network and hard resource caps (see
    # app/tools/sandbox.py); it is allowed at tier 1 rather than gated, so the
    # agent can iterate on code without a human in the loop for every run.
    def check(self,tool,user):
        if tool not in self.risks:return PolicyResult(Decision.DENY,'TOOL_NOT_REGISTERED')
        risk=self.risks[tool]
        if risk>=2:return PolicyResult(Decision.REQUIRE_APPROVAL,'RISK_TIER_REQUIRES_REVIEW')
        # The verified identity's role is always a tier role (admin/higher/lower); the
        # client's originally requested role is preserved separately as requested_role.
        # The approval-gate demo keys off that, so it works over HTTP and from the CLI.
        if tool in ('generate_docx','generate_xlsx','generate_pptx','generate_pdf'): return PolicyResult(Decision.REQUIRE_APPROVAL,'DOCUMENT_ARTIFACT_REQUIRES_REVIEW') if 'approver_demo' in {user.get('requested_role'), user.get('role')} else PolicyResult(Decision.ALLOW,'LOW_RISK_CONFIGURED')
        return PolicyResult(Decision.ALLOW,'LOW_RISK_CONFIGURED')
