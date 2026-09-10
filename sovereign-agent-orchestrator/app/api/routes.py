import asyncio, uuid, mimetypes, shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse
from app.schemas.contracts import *
from app.auth import current_identity
router=APIRouter(prefix='/api/v1')
SERVICE=None

def init_service(s):
 global SERVICE; SERVICE=s
@router.get('/health')
def health(): return {'status':'ok'}
@router.get('/ready')
def ready(): return {'status':'ready'}
@router.get('/tools')
def list_tools(identity: dict=Depends(current_identity)): return {'tools': SERVICE.tools.names()}
@router.get('/models')
def list_models(identity: dict=Depends(current_identity)): return {'models': [{'id': m['id'], 'model': m.get('model'), 'capabilities': m.get('capabilities', []), 'enabled': m.get('enabled', False), 'tier': m.get('tier')} for m in SERVICE.router.models]}
@router.post('/files')
async def upload(file: UploadFile=File(...), identity: dict=Depends(current_identity)):
 fid=str(uuid.uuid4()); p=SERVICE.workspace.root/'uploads'; p.mkdir(exist_ok=True); dest=p/(fid+'_'+Path(file.filename or 'upload').name)
 data=await file.read(); dest.write_bytes(data)
 try:
  indexed=await SERVICE.tools.rag.ingest(dest, {'mime_type':file.content_type,'file_id':fid,'tenant_id':identity['tenant_id'],'clearance':identity['clearance']})
 except ValueError as exc:
  raise HTTPException(400,str(exc)) from exc
 SERVICE.store.register_file(fid, identity['user_id'], identity['tenant_id'], file.filename or 'upload', str(dest), {'mime_type':file.content_type, 'index':indexed})
 SERVICE.store.audit(identity['user_id'], identity['tenant_id'], 'file_indexed', fid, indexed)
 return {'file_id':fid,'name':file.filename,'mime_type':file.content_type,'size_bytes':len(data),'index':indexed}
@router.post('/knowledge/search')
async def knowledge_search(request: dict, identity: dict=Depends(current_identity)):
 query=str(request.get('query','')).strip()
 if not query: raise HTTPException(422,'QUERY_REQUIRED')
 metadata=dict(request.get('metadata') or {}); metadata.update({'tenant_id': identity['tenant_id']})
 return {'hits':await SERVICE.tools.rag.search(query, int(request.get('top_k',5)), metadata)}
@router.post('/agent/run')
async def run(req:AgentRunRequest, identity: dict=Depends(current_identity)):
 jid=str(uuid.uuid4()); context=req.user_context.model_dump(); context.update(identity); context['requested_role']=req.user_context.role
 SERVICE.workspace.create(jid)
 attachments=[]
 for attachment in req.attachments:
  if not attachment.file_id: raise HTTPException(422,'ATTACHMENT_FILE_ID_REQUIRED')
  record=SERVICE.store.file_for(attachment.file_id, identity)
  if not record: raise HTTPException(403,'ATTACHMENT_NOT_AUTHORIZED')
  destination=SERVICE.workspace.safe(jid, 'input/'+Path(record['name']).name, True)
  shutil.copyfile(record['path'], destination)
  attachments.append({'file_id': record['id'], 'name': record['name'], 'path': str(destination.relative_to(SERVICE.workspace.root/jid)), 'mime_type': record['metadata']})
 j={'job_id':jid,'status':'queued','task':req.task,'user_context':context,'attachments':attachments,'routing':None,'plan':[],'tool_calls':[],'observations':[],'verification':None,'requires_human_approval':False,'approval':None,'artifacts':[],'final_answer':None,'error':None,'task_type':'document_workflow'}; SERVICE.store.save(j); SERVICE.store.enqueue(jid); SERVICE.store.audit(identity['user_id'], identity['tenant_id'], 'job_created', jid, {'task': req.task, 'attachments': [a['file_id'] for a in attachments]}); SERVICE._emit(j,'job_created',{'status':'queued'}); return {'job_id':jid,'status':'queued'}
@router.get('/agent/{job_id}')
def get_job(job_id, identity: dict=Depends(current_identity)):
 j=SERVICE.store.get(job_id)
 if not j: raise HTTPException(404,'JOB_NOT_FOUND')
 if j.get('user_context',{}).get('tenant_id') != identity['tenant_id']: raise HTTPException(404,'JOB_NOT_FOUND')
 return j
@router.post('/agent/{job_id}/approve')
async def approve(job_id,req:ApprovalRequest, identity: dict=Depends(current_identity)):
 j=get_job(job_id, identity)
 if not j: raise HTTPException(404,'JOB_NOT_FOUND')
 if j['status']!='awaiting_approval': raise HTTPException(409,'JOB_NOT_AWAITING_APPROVAL')
 await SERVICE.resume(j,req.approved,identity['user_id']); SERVICE.store.audit(identity['user_id'], identity['tenant_id'], 'approval_decision', job_id, {'approved': req.approved}); return {'job_id':job_id,'status':j['status']}
@router.post('/agent/{job_id}/cancel')
def cancel(job_id, identity: dict=Depends(current_identity)):
 j=get_job(job_id, identity)
 if not j: raise HTTPException(404,'JOB_NOT_FOUND')
 j['status']='cancelled'; SERVICE.store.save(j); SERVICE._emit(j,'job_cancelled',{}); return {'job_id':job_id,'status':'cancelled'}
@router.get('/agent/{job_id}/events')
def events(job_id, identity: dict=Depends(current_identity)):
 get_job(job_id, identity)
 async def gen():
  sent=0
  while True:
   rows=SERVICE.store.events(job_id)
   for e in rows[sent:]: yield f"event: {e['type']}\ndata: {__import__('json').dumps(e)}\n\n"
   sent=len(rows); j=SERVICE.store.get(job_id)
   if j and j['status'] in {'done','failed','cancelled'} and sent>=len(rows): break
   await asyncio.sleep(.25)
 return StreamingResponse(gen(),media_type='text/event-stream')
@router.get('/agent/{job_id}/artifacts')
def artifacts(job_id, identity: dict=Depends(current_identity)):
 j=get_job(job_id, identity)
 if not j: raise HTTPException(404,'JOB_NOT_FOUND')
 return j['artifacts']
@router.get('/agent/{job_id}/artifacts/{artifact_name}')
def artifact(job_id,artifact_name, identity: dict=Depends(current_identity)):
 get_job(job_id, identity)
 p=SERVICE.workspace.safe(job_id,'output/'+artifact_name)
 if not p.is_file(): raise HTTPException(404,'ARTIFACT_NOT_FOUND')
 return FileResponse(p,filename=p.name,media_type=mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
