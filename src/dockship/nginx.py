import os
import subprocess
from pathlib import Path

from dockship.config import settings

TEMPLATE = r"""server {
    listen 80;
    server_name ~^__NAME__\..+\.nip\.io$;
    location / {
        proxy_pass http://127.0.0.1:__PORT__;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
"""


def render(name: str, port: int) -> str:
    return TEMPLATE.replace("__NAME__", name).replace("__PORT__", str(port))


def apply(name: str, port: int) -> None:
    live = Path(settings.nginx_conf_dir) / f"{name}.conf"
    live.parent.mkdir(parents=True, exist_ok=True)
    old = live.read_text() if live.exists() else None
    temp = live.with_suffix(".conf.new")
    temp.write_text(render(name, port))
    os.replace(temp, live)
    try:
        subprocess.run(["sudo", "nginx", "-t"], check=True, capture_output=True)
        subprocess.run(
            ["sudo", "systemctl", "reload", "nginx"], check=True, capture_output=True
        )
    except subprocess.CalledProcessError:
        if old is None:
            live.unlink(missing_ok=True)
        else:
            live.write_text(old)
        raise
