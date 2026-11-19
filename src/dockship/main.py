import secrets

from fastapi import Depends, FastAPI, Header, HTTPException
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from dockship.apps import router as apps_router
from dockship.config import settings
from dockship.db import get_deployment, init_db, list_apps
from dockship.metrics import ACTIVE_APPS
from dockship.webhook import router as webhook_router


def require_key(x_api_key: str | None = Header(None)):
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.dockship_api_key):
        raise HTTPException(status_code=401, detail="invalid api key")


app = FastAPI(title="DockShip")
init_db()


@app.on_event("startup")
def startup() -> None:
    init_db()


app.include_router(apps_router, dependencies=[Depends(require_key)])
app.include_router(webhook_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics", dependencies=[Depends(require_key)])
def metrics():
    ACTIVE_APPS.set(len(list_apps()))
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/deployments/{deployment_id}", dependencies=[Depends(require_key)])
def deployment_status(deployment_id: str):
    deployment = get_deployment(deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="deployment not found")
    return deployment
