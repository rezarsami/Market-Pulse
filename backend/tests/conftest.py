import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Tests never make real API calls, but app.config.Settings reads
# ANTHROPIC_API_KEY at import time via get_client()'s runtime check, and
# several modules instantiate settings at import time -- set a dummy key
# so imports don't fail in CI/test environments that don't have secrets.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")
os.environ.setdefault("LOG_DIR", "./test_logs")
