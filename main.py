"""Search URL construction and run orchestration."""
import argparse
import re
from urllib.parse import quote, urlencode

import config
from automation import NaukriBot
from logger import get_logger

log = get_logger()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def build_search_url(keyword: str, location: str, freshness: str, page: int = 1, experience: float = 0) -> str:
    if freshness not in config.FRESHNESS_MAP:
        raise ValueError(f"freshness must be one of {list(config.FRESHNESS_MAP)}")
    locations = [loc.strip().lower() for loc in location.split(",") if loc.strip()]
    path = f"{slugify(keyword)}-jobs"
    if locations:
        path += "-in-" + "-".join(slugify(loc) for loc in locations)
    if page > 1:
        path += f"-{page}"
    query = {
        "k": keyword,
        config.FRESHNESS_PARAM: config.FRESHNESS_MAP[freshness],
        "experience": int(experience),
    }
    if locations:
        query["l"] = ", ".join(locations)
    return f"https://www.naukri.com/{path}?{urlencode(query, quote_via=quote)}"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Naukri auto-apply")
    ap.add_argument("--keywords", nargs="+", default=config.KEYWORDS)
    ap.add_argument("--location", default=config.LOCATION)
    ap.add_argument("--freshness", choices=list(config.FRESHNESS_MAP), default=config.FRESHNESS)
    ap.add_argument("--headless", action=argparse.BooleanOptionalAction, default=config.HEADLESS,
                    help="run without a visible browser window")
    ap.add_argument("--experience", type=float, default=config.EXPERIENCE_YEARS, help="your years of experience")
    ap.add_argument("--max", type=int, default=config.MAX_APPLICATIONS_PER_RUN, dest="max_apps")
    return ap.parse_args()


def run() -> None:
    args = parse_args()
    if not config.STATE_FILE.exists():
        raise SystemExit("naukri_state.json not found. Run `python auth.py` first.")
    config.HEADLESS = args.headless
    config.DEFAULT_ANSWERS["experience"] = str(args.experience)
    bot = NaukriBot(max_apps=args.max_apps, experience=args.experience)
    try:
        bot.run(
            args.keywords,
            args.location,
            args.freshness,
            lambda kw, loc, fr, pg: build_search_url(kw, loc, fr, pg, args.experience),
        )
    except KeyboardInterrupt:
        log.info("Interrupted by user.")
    log.info("Done. Applied this run: %d", bot.applied)
