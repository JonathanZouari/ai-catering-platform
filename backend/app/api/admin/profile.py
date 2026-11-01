from fastapi import APIRouter, UploadFile

from app.api.deps import ScopeDep, SessionDep, StorageDep
from app.repositories.caterers import get_own_caterer
from app.schemas.caterers import ProfileOut, ProfileUpdate
from app.services.common import apply_patch
from app.services.uploads import store_upload

router = APIRouter()


@router.get("/profile", response_model=ProfileOut)
def get_profile(session: SessionDep, scope: ScopeDep):
    return get_own_caterer(session, scope)


@router.patch("/profile", response_model=ProfileOut)
def update_profile(data: ProfileUpdate, session: SessionDep, scope: ScopeDep):
    caterer = get_own_caterer(session, scope)
    apply_patch(caterer, data)
    session.commit()
    return caterer


@router.post("/profile/logo", response_model=ProfileOut)
def upload_logo(file: UploadFile, session: SessionDep, scope: ScopeDep, storage: StorageDep):
    caterer = get_own_caterer(session, scope)
    caterer.logo_path = store_upload(storage, scope, "logos", file.file)
    session.commit()
    return caterer


@router.post("/profile/kashrut-certificate", response_model=ProfileOut)
def upload_kashrut_certificate(
    file: UploadFile, session: SessionDep, scope: ScopeDep, storage: StorageDep
):
    caterer = get_own_caterer(session, scope)
    caterer.kashrut_certificate_path = store_upload(
        storage, scope, "certificates", file.file, allow_pdf=True
    )
    session.commit()
    return caterer
