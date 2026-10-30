"""One-time manual login; saves the session to naukri_state.json."""
from playwright.sync_api import sync_playwright

import config


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.naukri.com/nlogin/login")
        input("Log in in the browser (solve OTP/Captcha), then press Enter here to save the session... ")
        context.storage_state(path=str(config.STATE_FILE))
        browser.close()
    print(f"Session saved to {config.STATE_FILE}")


if __name__ == "__main__":
    main()
