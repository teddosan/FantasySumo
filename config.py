"""
config.py — environment-based configuration lives here.

Local: values come from .env file
Production: values come from the host's environment variable UI
"""

import os, sys, json
from dotenv import load_dotenv

# reads .env if present, does nothing in production
load_dotenv()

def get_auth_config() -> dict:
    raw = os.environ.get('AUTH_CONFIG')

    if not raw:
        sys.exit("AUTH_CONFIG environment variable not set. See .env.example")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        sys.exit("AUTH_CONFIG is not valid JSON.")

DB_PATH = os.environ.get('DB_PATH', './sumo.db')
PORT    = int(os.environ.get('PORT', 8080))
