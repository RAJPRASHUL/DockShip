import hashlib
import hmac
import json

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from dockship import db
from dockship.apps import run_deploy
from dockship.config import settings
from dockship.models import norm_repo

router = APIRouter(tags=["webhook"])


def verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


@router.post("/webhook/github")
async def github(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
    x_github_delivery: str | None = Header(None),
):
    body = await request.body()
    if not verify_signature(
        body, x_hub_signature_256, settings.github_webhook_secret
    ):
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    if x_github_event == "ping":
        return {"msg": "pong"}
    if x_github_event != "push":
        return {"ignored": x_github_event}
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise TypeError("push payload must be an object")
        if payload.get("deleted"):
            return {"ignored": "branch deleted"}
        repository = payload["repository"]
        ref = payload["ref"]
        if not isinstance(repository, dict):
            raise TypeError("repository must be an object")
        clone_url = repository["clone_url"]
        if not isinstance(clone_url, str) or not isinstance(ref, str):
            raise TypeError("clone_url and ref must be strings")
        repo = norm_repo(clone_url)
        branch = ref.removeprefix("refs/heads/")
        if not branch:
            raise ValueError("missing branch")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid push payload") from exc

    if not x_github_delivery or not db.record_delivery(x_github_delivery):
        return {"ignored": "duplicate"}

    queued = []
    for app in db.find_apps(repo, branch):
        deployment_id = db.new_deployment(app["name"], "webhook")
        background_tasks.add_task(run_deploy, app["name"], deployment_id)
        queued.append(app["name"])
    return JSONResponse({"queued": queued}, status_code=202)
