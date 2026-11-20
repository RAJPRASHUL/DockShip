import subprocess
import time

import docker
import httpx
from docker import DockerClient
from docker.types import LogConfig

from dockship import db, nginx
from dockship.config import settings


def run_container(client: DockerClient, image: str, name: str, app: dict, port: int):
    return client.containers.run(
        image,
        name=name,
        detach=True,
        ports={"8000/tcp": ("127.0.0.1", port)},
        environment={"PORT": "8000"},
        restart_policy={"Name": "unless-stopped"},
        mem_limit="256m",
        nano_cpus=500_000_000,
        log_config=LogConfig(
            type="json-file", config={"max-size": "10m", "max-file": "3"}
        ),
    )


def remove_container(client: DockerClient, name: str) -> None:
    try:
        container = client.containers.get(name)
        container.remove(force=True)
    except docker.errors.NotFound:
        return


def healthy(container, port: int, path: str) -> bool:
    for _ in range(settings.health_tries):
        container.reload()
        if container.status != "running":
            return False
        try:
            if httpx.get(f"http://127.0.0.1:{port}{path}", timeout=2).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(settings.health_interval_s)
    return False


def deploy_image(
    client: DockerClient, app: dict, image: str, sha: str, deployment_id: str
) -> None:
    color = "green" if app["active_color"] == "blue" else "blue"
    port = app[f"{color}_port"]
    name = f"{app['name']}-{color}"
    remove_container(client, name)
    container = run_container(client, image, name, app, port)
    if not healthy(container, port, app["health_path"]):
        error = container.logs(tail=50).decode(errors="replace")
        remove_container(client, name)
        db.update_deployment(deployment_id, status="failed", error=error[-4000:])
        return
    db.set_pending_release(app["name"], color, sha, deployment_id)
    try:
        nginx.apply(app["name"], port)
    except (OSError, subprocess.CalledProcessError) as exc:
        remove_container(client, name)
        db.update_deployment(
            deployment_id, status="failed", error=str(exc)[-4000:]
        )
        db.clear_pending_release(app["name"])
        return
    time.sleep(settings.drain_s)
    if app["active_color"]:
        remove_container(client, f"{app['name']}-{app['active_color']}")
    db.set_release(app["name"], color, sha)
    db.clear_pending_release(app["name"])
    db.update_deployment(deployment_id, status="healthy", sha=sha)
    prune_images(client, app["name"], protect={sha})


def logs(client: DockerClient, app: dict, tail: int) -> str:
    color = app["active_color"]
    if not color:
        return ""
    container = client.containers.get(f"{app['name']}-{color}")
    return container.logs(tail=tail, timestamps=True).decode(errors="replace")


def prune_images(
    client: DockerClient, app_name: str, keep: int = 5, protect: set[str] | None = None
) -> None:
    protected = protect or set()
    images = client.images.list(name=f"dockship/{app_name}:")
    tagged = [
        (image.attrs.get("Created", 0), image, image.tags)
        for image in images
        if image.tags
    ]
    tagged.sort(key=lambda item: item[0], reverse=True)
    removable = tagged[keep:]
    for _, image, tags in removable:
        if any(
            tag.split(":")[-1][:12] in protected
            for tag in tags
            if tag.startswith(f"dockship/{app_name}:")
        ):
            continue
        try:
            client.images.remove(image.id, force=False)
        except docker.errors.ImageNotFound:
            continue
        except docker.errors.APIError:
            continue


def reconcile_pending_releases(client: DockerClient) -> None:
    from dockship.db import (
        clear_pending_release,
        list_pending_releases,
        set_release,
        update_deployment,
    )

    for app in list_pending_releases():
        color = app["pending_color"]
        sha = app["pending_sha"]
        deployment_id = app["pending_deployment_id"]
        name = f"{app['name']}-{color}"
        port = app[f"{color}_port"]
        try:
            container = client.containers.get(name)
            if not healthy(container, port, app["health_path"]):
                remove_container(client, name)
                clear_pending_release(app["name"])
                update_deployment(
                    deployment_id,
                    status="failed",
                    error="Pending release was unhealthy after restart",
                )
                continue
            nginx.apply(app["name"], port)
            time.sleep(settings.drain_s)
            if app["active_color"]:
                remove_container(client, f"{app['name']}-{app['active_color']}")
            set_release(app["name"], color, sha)
            clear_pending_release(app["name"])
            update_deployment(deployment_id, status="healthy", sha=sha)
            prune_images(client, app["name"], protect={sha})
        except (docker.errors.DockerException, OSError, subprocess.CalledProcessError):
            remove_container(client, name)
            clear_pending_release(app["name"])
            update_deployment(
                deployment_id,
                status="failed",
                error="Pending release could not be reconciled after restart",
            )
