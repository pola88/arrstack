import humanize


def format_torrent_status(torrent: dict) -> str:
    name = torrent.get("name", "?")[:45]
    pct = round(torrent.get("progress", 0) * 100)
    state = torrent.get("state", "?")
    dlspeed = humanize.naturalsize(torrent.get("dlspeed", 0)) + "/s"
    eta = torrent.get("eta", 0)

    if eta and eta < 8640000:  # ignore infinite ETAs
        eta_str = humanize.naturaldelta(eta)
    else:
        eta_str = "∞"

    return f"  • `{name}` — {pct}% @ {dlspeed} (ETA: {eta_str})"


def format_queue_item_radarr(item: dict) -> str:
    title = item.get("title", "?")[:45]
    status = item.get("status", "?")
    pct = round((1 - item.get("sizeleft", 1) / max(item.get("size", 1), 1)) * 100)
    return f"  • `{title}` — {pct}% [{status}]"


def format_queue_item_sonarr(item: dict) -> str:
    series = item.get("series", {}).get("title", "?")
    ep = item.get("episode", {})
    ep_code = f"S{ep.get('seasonNumber', 0):02d}E{ep.get('episodeNumber', 0):02d}"
    status = item.get("status", "?")
    pct = round((1 - item.get("sizeleft", 1) / max(item.get("size", 1), 1)) * 100)
    return f"  • `{series}` {ep_code} — {pct}% [{status}]"
