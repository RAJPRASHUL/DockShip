import json
import os
from pathlib import Path
from typing import Any

import httpx
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="DockShip command line interface")
console = Console()
CONFIG_PATH = Path.home() / ".dockship.json"


def load_config() -> dict[str, str]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"invalid {CONFIG_PATH}") from exc


def save_config(config: dict[str, str]) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")
    if os.name != "nt":
        CONFIG_PATH.chmod(0o600)


def request(method: str, path: str, **kwargs: Any) -> Any:
    config = load_config()
    server = config.get("server", "http://localhost:8000").rstrip("/")
    headers = kwargs.pop("headers", {})
    if config.get("api_key"):
        headers["X-API-Key"] = config["api_key"]
    try:
        response = httpx.request(method, server + path, headers=headers, **kwargs)
    except httpx.RequestError as exc:
        console.print(f"[red]request failed:[/red] {exc}")
        raise typer.Exit(1) from exc
    if response.is_error:
        console.print(response.text)
        raise typer.Exit(1)
    return response.json() if response.content else None


@app.command()
def login(
    server: str = typer.Option("http://localhost:8000"),
    api_key: str = typer.Option(..., prompt=True, hide_input=True),
) -> None:
    save_config({"server": server, "api_key": api_key})
    console.print(f"Saved configuration to {CONFIG_PATH}")


@app.command()
def register(
    name: str,
    repo_url: str,
    branch: str = "main",
    health_path: str = "/health",
) -> None:
    result = request(
        "POST",
        "/apps",
        json={
            "name": name,
            "repo_url": repo_url,
            "branch": branch,
            "health_path": health_path,
        },
    )
    console.print(result)


@app.command("list")
def list_apps() -> None:
    rows = request("GET", "/apps")
    table = Table("Name", "Repository", "Branch", "Status")
    for row in rows:
        table.add_row(
            row["name"],
            row["repo_url"],
            row["branch"],
            row["active_color"] or "not deployed",
        )
    console.print(table)


@app.command()
def deploy(name: str) -> None:
    console.print(request("POST", f"/apps/{name}/deploy"))


@app.command()
def logs(name: str, tail: int = 100) -> None:
    result = request("GET", f"/apps/{name}/logs", params={"tail": tail})
    console.print(result["logs"], end="")


@app.command()
def rollback(name: str) -> None:
    console.print(request("POST", f"/apps/{name}/rollback"))


@app.command()
def status(deployment_id: str) -> None:
    console.print(request("GET", f"/deployments/{deployment_id}"))


@app.command()
def delete(name: str) -> None:
    request("DELETE", f"/apps/{name}")
    console.print(f"Deleted {name}")
