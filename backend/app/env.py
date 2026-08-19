from pathlib import Path
from dotenv import load_dotenv

# repo root = two levels up from app/env.py
load_dotenv(Path(__file__).resolve().parents[2] / ".env")
