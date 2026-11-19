import secrets

from fastapi import Depends, FastAPI, Header, HTTPException

from dockship.apps import router as apps_router
from dockship.config import settings
from dockship.db import init_db


def require_key(x_api_key: str | None = Header(None)):
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.dockship_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")


app = FastAPI(title="DockShip")
init_db()


@app.on_event("startup")
def startup() -> None:
    init_db()


app.include_router(apps_router, dependencies=[Depends(require_key)])


@app.get("/health")
def health():
    return {"status": "ok"}
