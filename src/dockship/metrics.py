from prometheus_client import Counter, Gauge, Histogram

DEPLOYMENTS = Counter(
    "dockship_deployments_total",
    "Completed DockShip deployments by status.",
    ["status"],
)
DEPLOY_DURATION = Histogram(
    "dockship_deploy_duration_seconds",
    "Time spent running a deployment.",
)
ACTIVE_APPS = Gauge(
    "dockship_apps_active",
    "Number of registered DockShip applications.",
)


def record_deployment(status: str, duration: float) -> None:
    DEPLOYMENTS.labels(status=status).inc()
    DEPLOY_DURATION.observe(duration)
