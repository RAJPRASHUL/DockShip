from docker import DockerClient

from dockship.config import settings
from dockship.db import connect


def allocate_ports() -> tuple[int, int]:
    with connect() as conn:
        used = {
            port
            for row in conn.execute("SELECT blue_port, green_port FROM apps")
            for port in (row["blue_port"], row["green_port"])
            if port is not None
        }
    available = [
        port for port in range(settings.port_min, settings.port_max + 1) if port not in used
    ]
    if len(available) < 2:
        raise RuntimeError("no port pair available")
    return available[0], available[1]


def reconcile_containers(client: DockerClient) -> list[str]:
    with connect() as conn:
        known = {
            port
            for row in conn.execute("SELECT blue_port, green_port FROM apps")
            for port in (row["blue_port"], row["green_port"])
            if port is not None
        }
    warnings = []
    for container in client.containers.list(all=True):
        name = container.name
        if name.endswith(("-blue", "-green")):
            ports = container.attrs.get("HostConfig", {}).get("PortBindings", {})
            container_ports = {
                int(binding["HostPort"])
                for bindings in ports.values()
                for binding in bindings or []
                if binding.get("HostPort", "").isdigit()
            }
            if not container_ports.intersection(known):
                warnings.append(name)
    return warnings
