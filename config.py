"""User preferences and rate limits."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# KEYWORDS = [
#     # Digital Marketing & Content
#     "Digital Marketing Fresher",
#     "Social Media Executive Trainee",
#     "Junior SEO Analyst",
#     "Content Writer Fresher",
#     "Copywriter Trainee",
#     "Junior Performance Marketer",
#     "Email Marketing Associate",
#     "Google Ads Fresher",
#     "Canva / Graphic Design Associate",

#     # Sales, Business Development & Operations
#     "Business Development Associate (BDA)",
#     "Inside Sales Executive Fresher",
#     "Client Relationship Executive",
#     "Management Trainee Sales",
#     "Operations Executive Fresher",
#     "Business Operations Analyst Trainee",
#     "Lead Generation Executive",
#     "Account Manager Trainee",

#     # Human Resources & Talent Acquisition
#     "HR Recruiter Fresher",
#     "HR Generalist Trainee",
#     "Talent Acquisition Executive",
#     "HR Intern",
#     "Human Resources Associate",
#     "Payroll Associate Fresher",
#     "Employee Engagement Specialist",

#     # Finance, Banking & Accounting
#     "Junior Accountant",
#     "Finance Trainee",
#     "Financial Analyst Fresher",
#     "Tax Associate Fresher",
#     "Audit Associate Trainee",
#     "Bank Associate / Graduate Trainee",
#     "Investment Banking Analyst Fresher",
#     "Accounts Payable / Receivable Executive",

#     # Customer Service & Client Support
#     "Customer Support Associate",
#     "Customer Relationship Officer",
#     "Technical Support Executive (Non-Voice)",
#     "Customer Success Associate",
#     "Client Servicing Executive",
#     "Helpdesk Analyst Fresher",

#     # Supply Chain, Logistics & E-Commerce
#     "Logistics Executive Fresher",
#     "Supply Chain Trainee",
#     "Procurement Associate",
#     "E-commerce Operations Executive",
#     "Inventory Associate",
#     "Warehouse Operations Trainee"
# ]

# Search
KEYWORDS = [
    # "ServiceNow Fresher",
    # "Junior ServiceNow Developer",
    "JavaScript Developer Fresher",
    "Junior Frontend Developer",
    "React.js Fresher",
    "Mobile App Developer Fresher",
    "React Native Fresher",
    "Junior Software Engineer",
    "Software Engineer Trainee"
]
# KEYWORDS = ["ServiceNow Fresher"]
# LOCATION = "Noida, Gr. Noida, Delhi"
LOCATION = "Noida, Pune, Bengaluru, Hyderabad"  # e.g. "Bengaluru"; empty = any
FRESHNESS = "3_days"  # "today" | "3_days" | "7_days" | "15_days"
EXPERIENCE_YEARS = 0.5  # your total experience in years (0, 4, 12, ...)
# Skip jobs whose upper experience bound exceeds EXPERIENCE_YEARS + this (e.g. 0.5 + 1 skips "0-3 Yrs").
EXPERIENCE_TOLERANCE_YEARS = 1

FRESHNESS_MAP = {"today": 1, "3_days": 3, "7_days": 7, "15_days": 15}
# Naukri's live filter parameter is `jobAge`; change to "fgn" if you prefer the legacy name.
FRESHNESS_PARAM = "jobAge"

# Limits and pacing
MAX_APPLICATIONS_PER_RUN = 20
MAX_PAGES_PER_KEYWORD = 3
MIN_DELAY_SEC = 3
MAX_DELAY_SEC = 7

# Browser
HEADLESS = False  # Naukri returns "Access Denied" to headless browsers, so keep False
BLOCK_HEAVY_RESOURCES = True  # skip images, fonts and media to load pages faster
NAV_TIMEOUT_MS = 30_000

# Questionnaire defaults (used only for simple text/number fields)
DEFAULT_ANSWERS = {
    "experience": str(EXPERIENCE_YEARS),
    "ctc": "0",
    "notice": "0",
    "default": "Yes",
}

# Files
STATE_FILE = BASE_DIR / "naukri_state.json"
HISTORY_FILE = BASE_DIR / "applications_history.csv"
LOG_FILE = BASE_DIR / "jobapp.log"

# LinkedIn (separate run: python linkedin_app.py)
LINKEDIN_KEYWORDS = KEYWORDS
LINKEDIN_LOCATION = LOCATION  # one search per comma-separated location
LINKEDIN_MAX_APPLICATIONS_PER_RUN = 10
LINKEDIN_MAX_PAGES_PER_KEYWORD = 2
# Titles containing these words are skipped (LinkedIn has no experience range on cards).
LINKEDIN_EXCLUDE_TITLE_WORDS = ["senior", "sr", "lead", "principal", "manager", "architect", "head", "director", "staff"]
LINKEDIN_STATE_FILE = BASE_DIR / "linkedin_state.json"
LINKEDIN_HISTORY_FILE = BASE_DIR / "linkedin_history.csv"
LINKEDIN_LOG_FILE = BASE_DIR / "linkedin.log"
