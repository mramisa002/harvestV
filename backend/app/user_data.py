"""Anonymous browser-scoped persistence. Device bearer tokens are not user accounts."""
import hashlib
import json
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from .db import connect, query, get_district

router=APIRouter(prefix='/api/v1')
Token=Annotated[str,Header(alias='X-Device-Token',pattern=r'^[0-9a-f]{64}$')]

def owner(token):
    import re
    if not isinstance(token,str) or not re.fullmatch('[0-9a-f]{64}',token): raise HTTPException(401,'A valid device token is required.')
    return hashlib.sha256(token.encode()).hexdigest()

def initialize_user_data():
    with connect() as db:
        for ddl in [
            'CREATE TABLE IF NOT EXISTS farms (owner TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)',
            'CREATE TABLE IF NOT EXISTS feedback (owner TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(owner,id))',
            'CREATE TABLE IF NOT EXISTS saved_advisories (owner TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(owner,id))']:
            query(db,ddl)

class FarmInput(BaseModel):
    district_id:str=Field(min_length=2,max_length=60)
    fields:dict[str,str]=Field(default_factory=dict,max_length=30)
    @field_validator('fields')
    @classmethod
    def bounded_fields(cls,fields):
        if any(len(k)>60 or len(v)>1000 for k,v in fields.items()): raise ValueError('Farm fields exceed allowed length')
        return fields

class FeedbackInput(BaseModel):
    id:UUID
    message:str=Field(min_length=1,max_length=5000)
    rating:Literal['helpful','needs_adjustment']|None=None
    district_id:str|None=Field(default=None,max_length=60)
    @field_validator('message')
    @classmethod
    def nonblank(cls,value):
        value=value.strip()
        if not value: raise ValueError('Write an observation first')
        return value

class SaveInput(BaseModel):
    id:UUID
    district_id:str=Field(min_length=2,max_length=60)
    crop:Literal['wheat','mustard','lentil','potato']
    lang:Literal['en','bn']='en'

@router.get('/farm')
def get_farm(x_device_token:Token):
    with connect() as db:
        r=query(db,'SELECT payload,updated_at FROM farms WHERE owner=?',(owner(x_device_token),)).fetchone()
        return {'farm':json.loads(r['payload']) if r else None,'updated_at':r['updated_at'] if r else None}

@router.put('/farm')
def put_farm(body:FarmInput,x_device_token:Token):
    now=datetime.now(timezone.utc).isoformat()
    with connect() as db:
        if not get_district(db,body.district_id): raise HTTPException(404,'Unknown district')
        query(db,'INSERT INTO farms(owner,payload,updated_at) VALUES (?,?,?) ON CONFLICT(owner) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at',
              (owner(x_device_token),body.model_dump_json(),now))
    return {'farm':body.model_dump(),'updated_at':now}

def list_items(table,token):
    with connect() as db:
        rows=query(db,f'SELECT id,payload,created_at FROM {table} WHERE owner=? ORDER BY created_at DESC LIMIT 50',(owner(token),)).fetchall()
        return [{'id':r['id'],'created_at':r['created_at'],**json.loads(r['payload'])} for r in rows]

@router.get('/feedback')
def get_feedback(x_device_token:Token): return list_items('feedback',x_device_token)

@router.post('/feedback')
def post_feedback(body:FeedbackInput,x_device_token:Token):
    key=owner(x_device_token); now=datetime.now(timezone.utc).isoformat()
    with connect() as db:
        if body.district_id and not get_district(db,body.district_id): raise HTTPException(404,'Unknown district')
        query(db,'INSERT INTO feedback(owner,id,payload,created_at) VALUES (?,?,?,?) ON CONFLICT(owner,id) DO NOTHING',
              (key,str(body.id),body.model_dump_json(exclude={'id'}),now))
    return {'id':str(body.id),'status':'stored','expert_review':'not_connected','attachments_uploaded':False}

@router.get('/saved-advisories')
def get_saved(x_device_token:Token): return list_items('saved_advisories',x_device_token)

@router.post('/saved-advisories')
def save_advisory(body:SaveInput,x_device_token:Token):
    key=owner(x_device_token)
    with connect() as db:
        existing=query(db,'SELECT id FROM saved_advisories WHERE owner=? AND id=?',(key,str(body.id))).fetchone()
    if existing: return {'id':str(body.id),'status':'stored'}
    from .main import advisory
    result=advisory(body.district_id,body.crop,body.lang,14)
    now=datetime.now(timezone.utc).isoformat()
    with connect() as db:
        query(db,'INSERT INTO saved_advisories(owner,id,payload,created_at) VALUES (?,?,?,?) ON CONFLICT(owner,id) DO NOTHING',
              (key,str(body.id),json.dumps(result,default=str),now))
    return {'id':str(body.id),'status':'stored'}

class CheckInput(BaseModel):
    advice:str=Field(min_length=1,max_length=5000)
    lang:Literal['en','bn']='en'

@router.post('/information-check')
def information_check(body:CheckInput):
    if not body.advice.strip(): raise HTTPException(422,'Enter the advice to check')
    return {'status':'UNVERIFIED','sources':[], 'message':
            'নির্ভরযোগ্য সূত্র খোঁজার সেবা সংযুক্ত নেই। এই পরামর্শ যাচাই করা যায়নি।' if body.lang=='bn' else
            'Reference retrieval is not connected. This advice could not be verified; no supporting sources were found or checked.'}
