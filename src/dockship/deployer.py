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
    try:
        nginx.apply(app["name"], port)
    except (OSError, subprocess.CalledProcessError) as exc:
        remove_container(client, name)
        db.update_deployment(
            deployment_id, status="failed", error=str(exc)[-4000:]
        )
        return
    time.sleep(settings.drain_s)
    if app["active_color"]:
        remove_container(client, f"{app['name']}-{app['active_color']}")
    db.set_release(app["name"], color, sha)
    db.update_deployment(deployment_id, status="healthy", sha=sha)


def logs(client: DockerClient, app: dict, tail: int) -> str:
    color = app["active_color"]
    if not color:
        return ""
    container = client.containers.get(f"{app['name']}-{color}")
    return container.logs(tail=tail, timestamps=True).decode(errors="replace")
