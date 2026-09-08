import argparse, asyncio, json
from app.config import settings
from app.storage.store import Store
from app.workspace.manager import Workspace
from app.models.router import ModelRouter
from app.policy.engine import Policy
from app.tools.registry import ToolRegistry
from app.verification.verifier import Verifier
from app.orchestrator.service import Orchestrator
async def main():
 p=argparse.ArgumentParser(); p.add_argument('task',nargs='?',default='Read the inspection report and generate an approval note citing the applicable SOP.'); p.add_argument('--approval',action='store_true'); a=p.parse_args(); store=Store(settings.database_url); ws=Workspace(settings.workspace_root); svc=Orchestrator(store,ws,ModelRouter('config/models.yaml'),Policy(),ToolRegistry(ws),Verifier()); jid=__import__('uuid').uuid4().hex; j={'job_id':jid,'status':'queued','task':a.task,'user_context':{'user_id':'cli-user','role':'approver_demo' if a.approval else 'user','department':'inspection','clearance':'internal','project':'demo'},'routing':None,'plan':[],'tool_calls':[],'observations':[],'verification':None,'requires_human_approval':False,'approval':None,'artifacts':[],'final_answer':None,'error':None}; store.save(j); await svc.run(j); print(json.dumps(store.get(jid),indent=2));
 if store.get(jid)['status']=='awaiting_approval': print(f'Approval required. Run: python cli.py --approve {jid}')
if __name__=='__main__': asyncio.run(main())
