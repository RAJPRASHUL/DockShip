import shutil
import subprocess
import tempfile
from pathlib import Path


def _run(cmd: list[str], timeout: int) -> str:
    result = subprocess.run(
        cmd, check=False, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode:
        raise RuntimeError((result.stdout + result.stderr)[-4000:])
    return result.stdout.strip()


def clone(repo_url: str, branch: str) -> tuple[Path, str]:
    working_dir = Path(tempfile.mkdtemp(prefix="dockship-"))
    try:
        _run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                branch,
                "--",
                repo_url,
                str(working_dir),
            ],
            60,
        )
        return working_dir, _run(["git", "-C", str(working_dir), "rev-parse", "HEAD"], 10)
    except Exception:
        cleanup(working_dir)
        raise


def build(working_dir: Path, app: str, sha: str) -> str:
    tag = f"dockship/{app}:{sha[:12]}"
    _run(["docker", "build", "-t", tag, str(working_dir)], 300)
    return tag


def cleanup(working_dir: Path) -> None:
    shutil.rmtree(working_dir, ignore_errors=True)
