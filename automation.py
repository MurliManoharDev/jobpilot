"""Core Playwright interactions."""
import random
import re
import time

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PWTimeout

import config
import tracker
from logger import get_logger

log = get_logger()

CARD_LINK = "div.srp-jobtuple-wrapper a.title, div.cust-job-tuple a.title, article.jobTuple a.title"
APPLY_BTN = "#apply-button, button:has-text('Apply'):not(:has-text('Company')):not(:has-text('company'))"
COMPANY_SITE_BTN = "#company-site-button, button:has-text('Apply on company site'), a:has-text('Apply on company site')"
ALREADY_APPLIED = "#already-applied, button:has-text('Already Applied'), div:has-text('You have already applied')"
SUCCESS_MARKERS = "text=/successfully applied|application (has been )?sent/i"
CHATBOT = "[class*='chatbot_Drawer'], [class*='chatbot_Container']"


# Level words describe seniority, not the role, so they are not required in the job text.
GENERIC_WORDS = {"fresher", "freshers", "junior", "trainee", "senior", "entry", "level", "intern"}
# Naukri may display a city under its alternate name.
LOCATION_ALIASES = {"bengaluru": ["bangalore"], "gurgaon": ["gurugram"], "mumbai": ["navi mumbai"]}


def human_delay(lo: float = config.MIN_DELAY_SEC, hi: float = config.MAX_DELAY_SEC) -> None:
    time.sleep(random.uniform(lo, hi))


class NaukriBot:
    def __init__(self, max_apps: int, experience: int = 0):
        self.max_apps = max_apps
        self.experience = experience
        self.applied = 0
        self.seen = tracker.load_seen_urls()
        self.freshness = config.FRESHNESS
        self._core_tokens: list[str] = []
        self._location_terms: list[str] = []

    def run(self, keywords, location, freshness, url_builder) -> None:
        self.freshness = freshness
        names = [c.strip().lower() for c in location.split(",") if c.strip()]
        self._location_terms = [t for n in names for t in [n, *LOCATION_ALIASES.get(n, [])]] or [""]
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=config.HEADLESS)
            context = browser.new_context(storage_state=str(config.STATE_FILE))
            context.set_default_timeout(config.NAV_TIMEOUT_MS)
            if config.BLOCK_HEAVY_RESOURCES:
                context.route(
                    "**/*",
                    lambda route: route.abort()
                    if route.request.resource_type in {"image", "font", "media"}
                    else route.continue_(),
                )
            search_page = context.new_page()
            try:
                for kw in keywords:
                    self._core_tokens = self._tokens(kw)
                    for pg in range(1, config.MAX_PAGES_PER_KEYWORD + 1):
                        if self.applied >= self.max_apps:
                            return
                        url = url_builder(kw, location, freshness, pg)
                        log.info("Searching: %s", url)
                        links = self._collect_links(search_page, url)
                        if not links:
                            break
                        for link in links:
                            if self.applied >= self.max_apps:
                                log.info("Reached cap of %d applications.", self.max_apps)
                                return
                            self._process_job(context, link)
            finally:
                context.storage_state(path=str(config.STATE_FILE))
                browser.close()

    def _collect_links(self, page: Page, url: str) -> list[str]:
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_selector(CARD_LINK, timeout=15_000)
        except PWTimeout:
            log.warning("No job cards found. Page title: %r (\"Access Denied\" means headless is blocked).", page.title())
            return []
        human_delay(2, 4)
        hrefs = page.eval_on_selector_all(CARD_LINK, "els => els.map(e => e.href)")
        unique, out = set(), []
        for h in hrefs:
            if not h:
                continue
            key = tracker.normalize_url(h)
            if key not in unique:
                unique.add(key)
                out.append(h)
        return out

    def _process_job(self, context, url: str) -> None:
        key = tracker.normalize_url(url)
        if key in self.seen:
            log.info("Skip (already in history): %s", url)
            return
        page = context.new_page()
        title, company = "Unknown", "Unknown"
        try:
            page.goto(url, wait_until="domcontentloaded")
            human_delay()
            title = self._text(page, "h1") or title
            company = self._text(page, "[class*='comp-name'], a[class*='jd-header-comp-name']") or company
            log.info("Checking: %s @ %s", title, company)

            reason = self._mismatch_reason(page, title)
            if reason:
                self._finish(key, title, company, url, f"Skipped - {reason} Mismatch")
                return
            if page.locator(ALREADY_APPLIED).first.is_visible():
                self._finish(key, title, company, url, "Already Applied")
                return
            if page.locator(COMPANY_SITE_BTN).first.is_visible():
                self._finish(key, title, company, url, "Skipped - External")
                return
            btn = page.locator(APPLY_BTN).first
            if not btn.is_visible():
                self._finish(key, title, company, url, "Skipped - No Apply Button")
                return

            btn.click()
            human_delay()
            if page.locator(CHATBOT).first.is_visible():
                if not self._handle_questionnaire(page):
                    self._finish(key, title, company, url, "Skipped - Questionnaire")
                    return
            if page.locator(SUCCESS_MARKERS).first.is_visible() or self._confirmed_after_reload(page, url):
                self.applied += 1
                self._finish(key, title, company, url, "Applied")
                log.info("Applied %d/%d: %s @ %s", self.applied, self.max_apps, title, company)
            else:
                self._finish(key, title, company, url, "Unconfirmed")
        except Exception as e:  # noqa: BLE001 - one bad job must not stop the run
            log.error("Error on %s: %s", url, e)
            tracker.record(title, company, url, "Error")
        finally:
            page.close()
            human_delay()

    def _finish(self, key, title, company, url, status) -> None:
        self.seen.add(key)
        tracker.record(title, company, url, status)
        if status != "Applied":
            log.info("%s: %s", status, url)

    def _confirmed_after_reload(self, page: Page, url: str) -> bool:
        """Reload the job page; Naukri shows 'Applied' there only if the application went through."""
        page.goto(url, wait_until="domcontentloaded")
        human_delay(1, 2)
        return page.locator(ALREADY_APPLIED).first.is_visible()

    def _mismatch_reason(self, page: Page, title: str) -> str:
        """Return the first config criterion the job fails (empty string if it matches)."""
        skills = self._text(page, "[class*='key-skill'], [class*='skill']")
        if not self._keyword_matches(f"{title} {skills}"):
            return "Keyword"

        exp = re.search(r"(\d+)\s*-\s*(\d+)\s*(?:Yrs?|Years?)", self._text(page, "body"), re.I)
        if exp:
            low, high = int(exp.group(1)), int(exp.group(2))
            if low > self.experience or high > self.experience + config.EXPERIENCE_TOLERANCE_YEARS:
                return "Experience"

        loc = self._text(page, "[class*='loc']").lower()
        if loc and not any(a in loc for a in self._location_terms):
            return "Location"

        posted = re.search(r"posted:?\s*(\d+)\+?\s*days?\s*ago", self._text(page, "body"), re.I)
        if posted and int(posted.group(1)) > config.FRESHNESS_MAP[self.freshness]:
            return "Freshness"
        return ""

    def _keyword_matches(self, text: str) -> bool:
        norm = text.lower().replace(".", "")
        return all(tok in norm for tok in self._core_tokens)

    @staticmethod
    def _tokens(keyword: str) -> list[str]:
        words = re.split(r"\s+", keyword.lower().replace(".", "").strip())
        return [w for w in words if w and w not in GENERIC_WORDS]

    @staticmethod
    def _text(page: Page, selector: str) -> str:
        loc = page.locator(selector).first
        try:
            return loc.inner_text(timeout=3000).strip()
        except PWTimeout:
            return ""

    def _handle_questionnaire(self, page: Page) -> bool:
        """Fill simple text fields / pick first radio option; return True if submission confirmed."""
        for _ in range(8):
            drawer = page.locator(CHATBOT).first
            if page.locator(SUCCESS_MARKERS).first.is_visible() or not drawer.is_visible():
                return True
            filled = False
            for radio in drawer.locator("input[type='radio']").all()[:1]:
                radio.scroll_into_view_if_needed()
                radio.check(force=True)
                filled = True
            for box in drawer.locator("[contenteditable='true'], input[type='text'], input[type='number']").all():
                if box.is_visible():
                    box.fill(self._answer_for(drawer.inner_text()))
                    filled = True
            save = drawer.locator("button:has-text('Save'), button:has-text('Submit'), div.sendMsg").first
            if not (filled and save.is_visible()):
                return False
            save.click()
            human_delay(2, 4)
        return False

    @staticmethod
    def _answer_for(question: str) -> str:
        q = question.lower()
        if "notice" in q:
            return config.DEFAULT_ANSWERS["notice"]
        if "ctc" in q or "salary" in q:
            return config.DEFAULT_ANSWERS["ctc"]
        if "experience" in q or "years" in q:
            return config.DEFAULT_ANSWERS["experience"]
        return config.DEFAULT_ANSWERS["default"]
