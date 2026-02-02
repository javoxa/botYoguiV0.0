import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent
os.chdir(PROJECT_ROOT)

load_dotenv(PROJECT_ROOT / ".env")

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

INFERENCE_API_URL = os.getenv(
    "INFERENCE_API_URL",
    "http://localhost:8000/generate"
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://unsa_admin:unsa_password@localhost/unsa_knowledge_db"
)

# Configuración de timeouts y límites
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "32"))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "15.0"))
RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "2"))
RETRY_DELAY = float(os.getenv("RETRY_DELAY", "1.0"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "15"))

if not TOKEN:
    print("❌ ERROR: TELEGRAM_TOKEN no configurado")
    sys.exit(1)

# ==================== LOGGING ====================
LOG_DIR = PROJECT_ROOT / "frontend" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

log_level = logging.DEBUG if DEBUG_MODE else logging.INFO

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "bot_postgres.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("unsa_bot")
