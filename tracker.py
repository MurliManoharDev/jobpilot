"""Read/write applications_history.csv."""
import csv
from datetime import datetime
from urllib.parse import urlsplit

import config

FIELDS = ["Job Title", "Company", "URL", "Date Applied", "Status"]


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.netloc}{parts.path}".rstrip("/").lower()


def _ensure_file(path) -> None:
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()


def load_seen_urls(path=config.HISTORY_FILE) -> set[str]:
    """URLs already handled (any status except transient failures) so they are not retried."""
    _ensure_file(path)
    with path.open(newline="", encoding="utf-8") as f:
        return {
            normalize_url(row["URL"])
            for row in csv.DictReader(f)
            if row.get("URL") and row.get("Status") != "Error"
        }


def record(title: str, company: str, url: str, status: str, path=config.HISTORY_FILE) -> None:
    _ensure_file(path)
    with path.open("a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writerow(
            {
                "Job Title": title,
                "Company": company,
                "URL": url,
                "Date Applied": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Status": status,
            }
        )
