import shutil
import humanize


def get_disk_usage(path: str) -> dict:
    usage = shutil.disk_usage(path)
    pct = round(usage.used / usage.total * 100, 1)
    return {
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
        "pct": pct,
        "total_h": humanize.naturalsize(usage.total, binary=True),
        "used_h": humanize.naturalsize(usage.used, binary=True),
        "free_h": humanize.naturalsize(usage.free, binary=True),
    }
