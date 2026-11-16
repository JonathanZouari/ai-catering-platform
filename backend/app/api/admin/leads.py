from uuid import UUID

from fastapi import APIRouter

from app.api.deps import ScopeDep, SessionDep
from app.models.enums import LeadStage
from app.schemas.leads import LeadNoteCreate, LeadOut, LeadStageUpdate, LeadSummary
from app.services import leads

router = APIRouter(prefix="/leads")


@router.get("", response_model=list[LeadSummary])
def list_leads(session: SessionDep, scope: ScopeDep, stage: LeadStage | None = None):
    return leads.list_leads(session, scope, stage)


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: UUID, session: SessionDep, scope: ScopeDep):
    return leads.get_lead(session, scope, lead_id)


@router.patch("/{lead_id}/stage", response_model=LeadOut)
def change_stage(lead_id: UUID, data: LeadStageUpdate, session: SessionDep, scope: ScopeDep):
    return leads.change_stage(session, scope, lead_id, data)


@router.post("/{lead_id}/notes", response_model=LeadOut, status_code=201)
def add_note(lead_id: UUID, data: LeadNoteCreate, session: SessionDep, scope: ScopeDep):
    return leads.add_note(session, scope, lead_id, data)
