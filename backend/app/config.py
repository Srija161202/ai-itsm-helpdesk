import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
KB_DIR = Path(os.getenv("KB_DIR", BASE_DIR / "knowledge_base"))

MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB = os.getenv("MONGODB_DB", "itsm_helpdesk")

SN_INSTANCE = os.getenv("SERVICENOW_INSTANCE", "").strip()
SN_USER = os.getenv("SERVICENOW_USER", "")
SN_PASSWORD = os.getenv("SERVICENOW_PASSWORD", "")

USE_LLM = os.getenv("USE_LLM", "true").lower() == "true"
LLM_MODEL = os.getenv("LLM_MODEL", "google/flan-t5-base")
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "auto").lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
AUTO_ESCALATE = os.getenv("AUTO_ESCALATE", "false").lower() == "true"
PROVISION_SECONDS = int(os.getenv("PROVISION_SECONDS", "15"))
