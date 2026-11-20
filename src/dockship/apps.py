import sqlite3
import subprocess
import threading
import time

import docker
from fastapi import APIRouter, BackgroundTasks, HTTPException

from dockship import builder, db, nginx
from dockship.db import list_apps
from dockship.deployer import deploy_image, logs
from dockship.metrics import record_deployment
from dockship.models import AppCreate

router = APIRouter(prefix="/apps", tags=["apps"])
_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()
build_sem = threading.Semaphore(1)


def app_lock(name: str) -> threading.Lock:
    with _guard:
        return _locks.setdefault(name, threading.Lock())


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
        sqlite3.Error,
        docker.errors.DockerException,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def run_deploy(name: str, deployment_id: str) -> None:
    with app_lock(name):
        started = time.monotonic()
        working_dir = None
        try:
            app = db.get_app(name)
            if not app:
                raise RuntimeError("app not found")
            with build_sem:
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
            subprocess.CalledProcessError,
            docker.errors.DockerException,
        ) as exc:
            db.update_deployment(deployment_id, status="failed", error=str(exc)[-4000:])
        finally:
            if working_dir:
                builder.cleanup(working_dir)
            duration = time.monotonic() - started
            db.update_deployment(deployment_id, duration_s=duration)
            deployment = db.get_deployment(deployment_id)
            if deployment and deployment["status"] in {"healthy", "failed"}:
                record_deployment(deployment["status"], duration)


def run_rollback(name: str, deployment_id: str, sha: str) -> None:
    with app_lock(name):
        started = time.monotonic()
        try:
            app = db.get_app(name)
            if not app:
                raise RuntimeError("app not found")
            db.update_deployment(deployment_id, status="deploying")
            deploy_image(
                docker.from_env(),
                app,
                f"dockship/{name}:{sha[:12]}",
                sha,
                deployment_id,
            )
        except (
            OSError,
            RuntimeError,
            sqlite3.Error,
            subprocess.CalledProcessError,
            docker.errors.DockerException,
        ) as exc:
            db.update_deployment(deployment_id, status="failed", error=str(exc)[-4000:])
        finally:
            duration = time.monotonic() - started
            db.update_deployment(deployment_id, duration_s=duration)
            deployment = db.get_deployment(deployment_id)
            if deployment and deployment["status"] in {"healthy", "failed"}:
                record_deployment(deployment["status"], duration)


@router.post("/{name}/deploy", status_code=202)
def deploy(name: str, background_tasks: BackgroundTasks) -> dict:
    if not db.get_app(name):
        raise HTTPException(status_code=404, detail="app not found")
    deployment_id = db.new_deployment(name, "manual")
    background_tasks.add_task(run_deploy, name, deployment_id)
    return {"deployment_id": deployment_id}


@router.post("/{name}/rollback", status_code=202)
def rollback(name: str, background_tasks: BackgroundTasks) -> dict:
    app = db.get_app(name)
    if not app:
        raise HTTPException(status_code=404, detail="app not found")
    if not app["previous_sha"]:
        raise HTTPException(status_code=409, detail="nothing to roll back to")
    deployment_id = db.new_deployment(name, "rollback")
    db.update_deployment(deployment_id, sha=app["previous_sha"])
    background_tasks.add_task(run_rollback, name, deployment_id, app["previous_sha"])
    return {"deployment_id": deployment_id}


@router.delete("/{name}", status_code=204)
def delete(name: str) -> None:
    with app_lock(name):
        app = db.get_app(name)
        if not app:
            raise HTTPException(status_code=404, detail="app not found")
        client = docker.from_env()
        remove_names = [f"{name}-blue", f"{name}-green"]
        for container_name in remove_names:
            try:
                container = client.containers.get(container_name)
                container.remove(force=True)
            except docker.errors.NotFound:
                pass
        nginx.remove(name)
        if not db.delete_app(name):
            raise HTTPException(status_code=404, detail="app not found")


@router.get("/{name}/logs")
def app_logs(name: str, tail: int = 100) -> dict:
    app = db.get_app(name)
    if not app:
        raise HTTPException(status_code=404, detail="app not found")
    try:
        return {"logs": logs(docker.from_env(), app, max(1, min(tail, 1000)))}
    except docker.errors.NotFound:
        return {"logs": ""}
