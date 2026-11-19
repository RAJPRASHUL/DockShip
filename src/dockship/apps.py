from fastapi import APIRouter

from dockship.db import list_apps


router = APIRouter(prefix="/apps", tags=["apps"])


@router.get("")
def apps() -> list[dict]:
    return list_apps()
