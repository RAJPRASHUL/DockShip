import sqlite3
import time

import docker
from fastapi import APIRouter, BackgroundTasks, HTTPException

from dockship import builder, db
from dockship.db import list_apps
from dockship.deployer import deploy_image, logs
from dockship.models import AppCreate

router = APIRouter(prefix="/apps", tags=["apps"])


@router.get("")
def apps() -> list[dict]:
    return list_apps()


@router.post("", status_code=201)
def register_app(payload: AppCreate) -> dict:
    if db.get_app(payload.name):
        raise HTTPException(status_code=409, detail="app already exists")
    try:
        return db.create_app(
            payload.name, payload.repo_url, payload.branch, payload.health_path
        )
    except (
        OSError,
        RuntimeError,
        TimeoutError,
        docker.errors.DockerException,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def run_deploy(name: str, deployment_id: str) -> None:
    started = time.monotonic()
    working_dir = None
    try:
        app = db.get_app(name)
        if not app:
            raise RuntimeError("app not found")
        db.update_deployment(deployment_id, status="building")
        working_dir, sha = builder.clone(app["repo_url"], app["branch"])
        image = builder.build(working_dir, name, sha)
        db.update_deployment(deployment_id, status="deploying", sha=sha)
        deploy_image(docker.from_env(), app, image, sha, deployment_id)
    except (
        OSError,
        RuntimeError,
        TimeoutError,
        sqlite3.Error,
        docker.errors.DockerException,
    ) as exc:
        db.update_deployment(deployment_id, status="failed", error=str(exc)[-4000:])
    finally:
        if working_dir:
            builder.cleanup(working_dir)
        db.update_deployment(deployment_id, duration_s=time.monotonic() - started)


@router.post("/{name}/deploy", status_code=202)
def deploy(name: str, background_tasks: BackgroundTasks) -> dict:
    if not db.get_app(name):
        raise HTTPException(status_code=404, detail="app not found")
    deployment_id = db.new_deployment(name, "manual")
    background_tasks.add_task(run_deploy, name, deployment_id)
    return {"deployment_id": deployment_id}


@router.get("/{name}/logs")
def app_logs(name: str, tail: int = 100) -> dict:
    app = db.get_app(name)
    if not app:
        raise HTTPException(status_code=404, detail="app not found")
    try:
        return {"logs": logs(docker.from_env(), app, max(1, min(tail, 1000)))}
    except docker.errors.NotFound:
        return {"logs": ""}
