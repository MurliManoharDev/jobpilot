"""LinkedIn Easy Apply automation."""
import re

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PWTimeout

import config
import tracker
from automation import GENERIC_WORDS, human_delay
from logger import get_logger

log = get_logger("linkedin", config.LINKEDIN_LOG_FILE)

CARD = "li[data-occludable-job-id], div[data-job-id]"
COMPANY = ".job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name"
DESCRIPTION = "#job-details, .jobs-description"
EASY_APPLY = "button.jobs-apply-button:has-text('Easy Apply'), button[aria-label^='Easy Apply']"
ANY_APPLY = "button.jobs-apply-button, a.jobs-apply-button"
APPLIED = ".artdeco-inline-feedback--success:has-text('Applied')"
MODAL = "div[role='dialog']"
SUBMIT = "button[aria-label='Submit application']"
NEXT = "button[aria-label='Continue to next step'], button[aria-label='Review your application']"
ERROR = ".artdeco-inline-feedback--error"
SENT = "text=/application (was )?sent/i"
GROUP = ".jobs-easy-apply-form-section__grouping, div[data-test-form-element]"


class LinkedInBot:
    def __init__(self, max_apps: int, experience: float):
        self.max_apps = max_apps
        self.experience = experience
        self.applied = 0
        self.seen = tracker.load_seen_urls(config.LINKEDIN_HISTORY_FILE)
        self.freshness = config.FRESHNESS
        self._core_tokens: list[str] = []

    def run(self, keywords, locations, freshness, url_builder) -> None:
        self.freshness = freshness
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=config.HEADLESS)
            context = browser.new_context(storage_state=str(config.LINKEDIN_STATE_FILE))
            context.set_default_timeout(config.NAV_TIMEOUT_MS)
            search_page = context.new_page()
            try:
                for kw in keywords:
                    self._core_tokens = self._tokens(kw)
                    for loc in locations:
                        for pg in range(1, config.LINKEDIN_MAX_PAGES_PER_KEYWORD + 1):
                            url = url_builder(kw, loc, freshness, pg)
                            log.info("Searching: %s", url)
                            ids = self._collect_ids(search_page, url)
                            if not ids:
                                break
                            for job_id in ids:
                                if self.applied >= self.max_apps:
                                    log.info("Reached cap of %d applications.", self.max_apps)
                                    return
                                self._process_job(context, f"https://www.linkedin.com/jobs/view/{job_id}/")
            finally:
                context.storage_state(path=str(config.LINKEDIN_STATE_FILE))
                browser.close()

    def _collect_ids(self, page: Page, url: str) -> list[str]:
        page.goto(url, wait_until="domcontentloaded")
        if re.search(r"login|authwall|checkpoint", page.url):
            raise RuntimeError("LinkedIn session invalid or verification required. Run `python linkedin_auth.py`.")
        try:
            page.wait_for_selector(CARD, timeout=15_000)
        except PWTimeout:
            log.warning("No job cards found. Page title: %r", page.title())
            return []
        for _ in range(5):  # cards load lazily as the list scrolls
            page.locator(CARD).last.scroll_into_view_if_needed()
            human_delay(1, 2)
        ids = page.eval_on_selector_all(
            CARD, "els => els.map(e => e.getAttribute('data-occludable-job-id') || e.getAttribute('data-job-id'))"
        )
        return list(dict.fromkeys(i for i in ids if i))

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
            company = self._text(page, COMPANY) or company
            log.info("Checking: %s @ %s", title, company)

            reason = self._mismatch_reason(page, title)
            if reason:
                self._finish(key, title, company, url, f"Skipped - {reason} Mismatch")
                return
            if page.locator(APPLIED).first.is_visible():
                self._finish(key, title, company, url, "Already Applied")
                return
            btn = page.locator(EASY_APPLY).first
            if not btn.is_visible():
                status = "Skipped - External" if page.locator(ANY_APPLY).first.is_visible() else "Skipped - No Apply Button"
                self._finish(key, title, company, url, status)
                return

            btn.click()
            human_delay()
            if not self._run_easy_apply(page):
                self._finish(key, title, company, url, "Skipped - Questionnaire")
                return
            if page.locator(SENT).first.is_visible() or self._confirmed_after_reload(page, url):
                self.applied += 1
                self._finish(key, title, company, url, "Applied")
                log.info("Applied %d/%d: %s @ %s", self.applied, self.max_apps, title, company)
            else:
                self._finish(key, title, company, url, "Unconfirmed")
        except Exception as e:  # noqa: BLE001 - one bad job must not stop the run
            log.error("Error on %s: %s", url, e)
            tracker.record(title, company, url, "Error", config.LINKEDIN_HISTORY_FILE)
        finally:
            page.close()
            human_delay()

    def _finish(self, key, title, company, url, status) -> None:
        self.seen.add(key)
        tracker.record(title, company, url, status, config.LINKEDIN_HISTORY_FILE)
        if status != "Applied":
            log.info("%s: %s", status, url)

    def _confirmed_after_reload(self, page: Page, url: str) -> bool:
        page.goto(url, wait_until="domcontentloaded")
        human_delay(1, 2)
        return page.locator(APPLIED).first.is_visible()

    def _mismatch_reason(self, page: Page, title: str) -> str:
        """Return the first config criterion the job fails (empty string if it matches)."""
        norm = title.lower().replace(".", "")
        if not all(tok in norm for tok in self._core_tokens):
            return "Keyword"
        words = set(re.findall(r"[a-z]+", norm))
        if words & set(config.LINKEDIN_EXCLUDE_TITLE_WORDS) and "senior" not in self._core_tokens:
            return "Seniority"
        desc = self._text(page, DESCRIPTION)
        years = [int(n) for n in re.findall(r"(\d{1,2})\s*\+?\s*(?:years|yrs)", desc, re.I)]
        if years and min(years) > self.experience + config.EXPERIENCE_TOLERANCE_YEARS:
            return "Experience"
        return ""

    @staticmethod
    def _tokens(keyword: str) -> list[str]:
        words = re.split(r"\s+", keyword.lower().replace(".", "").strip())
        return [w for w in words if w and w not in GENERIC_WORDS]

    @staticmethod
    def _text(page: Page, selector: str) -> str:
        try:
            return page.locator(selector).first.inner_text(timeout=3000).strip()
        except PWTimeout:
            return ""

    def _run_easy_apply(self, page: Page) -> bool:
        """Step through the Easy Apply dialog; return True once submitted."""
        for _ in range(12):
            modal = page.locator(MODAL).first
            if not modal.is_visible():
                return False
            self._fill_form(modal)
            submit = modal.locator(SUBMIT).first
            if submit.is_visible():
                follow = modal.locator("label[for*='follow-company-checkbox']").first
                if follow.is_visible() and modal.locator("input[id*='follow-company-checkbox']:checked").count():
                    follow.click()
                submit.click()
                human_delay(2, 4)
                self._dismiss(page, discard=False)
                return True
            nxt = modal.locator(NEXT).first
            if not nxt.is_visible():
                break
            nxt.click()
            human_delay(1, 2)
            if modal.locator(ERROR).first.is_visible():
                break
        self._dismiss(page, discard=True)
        return False

    @staticmethod
    def _dismiss(page: Page, discard: bool) -> None:
        close = page.locator("button[aria-label='Dismiss']").first
        if close.is_visible():
            close.click()
        if discard:
            confirm = page.locator("button[data-control-name='discard_application_confirm_btn'], button:has-text('Discard')").first
            try:
                confirm.click(timeout=3000)
            except PWTimeout:
                pass

    def _fill_form(self, modal) -> None:
        for group in modal.locator(GROUP).all():
            label = group.inner_text().lower()
            field = group.locator("input[type='text'], input[type='number'], textarea").first
            if field.count() and field.is_visible() and not field.input_value():
                numeric = field.get_attribute("type") == "number"
                field.fill(self._answer(label, numeric))
            select = group.locator("select").first
            if select.count() and select.input_value().lower().startswith("select"):
                try:
                    select.select_option(label="Yes")
                except Exception:  # noqa: BLE001 - option "Yes" may not exist
                    select.select_option(index=1)
            if group.locator("input[type='radio']").count() and not group.locator("input[type='radio']:checked").count():
                yes = group.locator("label:has-text('Yes')")
                (yes.first if yes.count() else group.locator("label").first).click()

    @staticmethod
    def _answer(label: str, numeric: bool) -> str:
        if "notice" in label:
            return config.DEFAULT_ANSWERS["notice"]
        if "ctc" in label or "salary" in label or "compensation" in label:
            return config.DEFAULT_ANSWERS["ctc"]
        if "experience" in label or "years" in label:
            return str(int(float(config.DEFAULT_ANSWERS["experience"])))
        return "0" if numeric else config.DEFAULT_ANSWERS["default"]
