import os
from dotenv import load_dotenv

load_dotenv()

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
MODEL = "claude-sonnet-4-6"

PERSONAL_INFO = {
    "first_name": os.getenv("FIRST_NAME", ""),
    "last_name": os.getenv("LAST_NAME", ""),
    "email": os.getenv("EMAIL", ""),
    "phone": os.getenv("PHONE", ""),
    "linkedin_url": os.getenv("LINKEDIN_URL", ""),
    "github_url": os.getenv("GITHUB_URL", ""),
    "portfolio_url": os.getenv("PORTFOLIO_URL", ""),
}
