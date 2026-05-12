"""Docker container stats via the Docker SDK."""

from typing import List, Tuple

from state import ContainerInfo


def get_containers() -> Tuple[List[ContainerInfo], bool]:
    """Return (containers, docker_available).  Never raises."""
    try:
        import docker  # type: ignore
        client = docker.from_env()
        client.ping()
    except Exception:
        return [], False

    results: List[ContainerInfo] = []
    try:
        for c in client.containers.list(all=True):
            info = ContainerInfo(name=c.name, status=c.status)
            if c.status == "running":
                try:
                    stats = c.stats(stream=False)
                    info.cpu_percent = _cpu_pct(stats)
                    info.mem_mb = (
                        stats.get("memory_stats", {}).get("usage", 0) / (1024 * 1024)
                    )
                except Exception:
                    pass
            results.append(info)
    except Exception:
        pass

    # running containers first, then stopped
    results.sort(key=lambda x: (x.status != "running", x.name))
    return results, True


def _cpu_pct(stats: dict) -> float:
    try:
        cpu_d = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        sys_d = (
            stats["cpu_stats"]["system_cpu_usage"]
            - stats["precpu_stats"]["system_cpu_usage"]
        )
        ncpus = stats["cpu_stats"].get("online_cpus", 1)
        if sys_d > 0:
            return (cpu_d / sys_d) * ncpus * 100.0
    except Exception:
        pass
    return 0.0
