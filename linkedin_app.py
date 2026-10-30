"""LinkedIn entry point: python linkedin_app.py [--keywords ...] [--location ...] [--freshness ...] [--experience N] [--max N]"""
import argparse
from urllib.parse import urlencode

import config
from linkedin_automation import LinkedInBot, log


def experience_levels(years: float) -> str:
    """Map years of experience to LinkedIn f_E codes (1 intern, 2 entry, 3 associate, 4 mid-senior, 5 director)."""
    if years < 2:
        return "1,2"
    if years <= 5:
        return "2,3"
    if years <= 10:
        return "3,4"
    return "4,5"


def build_search_url(keyword: str, location: str, freshness: str, page: int, experience: float) -> str:
    query = {
        "keywords": keyword,
        "f_AL": "true",  # Easy Apply only
        "f_TPR": f"r{config.FRESHNESS_MAP[freshness] * 86400}",
        "f_E": experience_levels(experience),
        "sortBy": "DD",
    }
    if location:
        query["location"] = location
    if page > 1:
        query["start"] = (page - 1) * 25
    return f"https://www.linkedin.com/jobs/search/?{urlencode(query)}"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="LinkedIn Easy Apply")
    ap.add_argument("--keywords", nargs="+", default=config.LINKEDIN_KEYWORDS)
    ap.add_argument("--location", default=config.LINKEDIN_LOCATION, help="comma-separated; one search each")
    ap.add_argument("--freshness", choices=list(config.FRESHNESS_MAP), default=config.FRESHNESS)
    ap.add_argument("--experience", type=float, default=config.EXPERIENCE_YEARS)
    ap.add_argument("--max", type=int, default=config.LINKEDIN_MAX_APPLICATIONS_PER_RUN, dest="max_apps")
    ap.add_argument("--headless", action=argparse.BooleanOptionalAction, default=config.HEADLESS)
    return ap.parse_args()


def run() -> None:
    args = parse_args()
    if not config.LINKEDIN_STATE_FILE.exists():
        raise SystemExit("linkedin_state.json not found. Run `python linkedin_auth.py` first.")
    config.HEADLESS = args.headless
    config.DEFAULT_ANSWERS["experience"] = str(args.experience)
    locations = [loc.strip() for loc in args.location.split(",") if loc.strip()] or [""]
    bot = LinkedInBot(max_apps=args.max_apps, experience=args.experience)
    try:
        bot.run(
            args.keywords,
            locations,
            args.freshness,
            lambda kw, loc, fr, pg: build_search_url(kw, loc, fr, pg, args.experience),
        )
    except KeyboardInterrupt:
        log.info("Interrupted by user.")
    except RuntimeError as e:
        log.error("%s", e)
    log.info("Done. Applied this run: %d", bot.applied)


if __name__ == "__main__":
    run()
