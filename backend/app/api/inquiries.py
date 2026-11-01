import logging

from fastapi import APIRouter, status

from app.schemas.inquiry import InquiryCreate

# uvicorn configures this logger at INFO; an app-level logger would be filtered out by default.
logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/api/inquiries", tags=["inquiries"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_inquiry(inquiry: InquiryCreate) -> dict[str, str]:
    # No database until Phase 2: inquiries are only written to the server log for now.
    logger.info("New inquiry: %s", inquiry.model_dump_json())
    return {"status": "received"}
