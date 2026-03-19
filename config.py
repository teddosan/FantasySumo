"""
config.py — all environment-based configuration lives here.

Locally: values come from .env file
Hosting: values come from the host's environment variable UI

Required environment variables:
    SECRET_KEY   — used to sign NiceGUI's session cookie (generate with: python -c "import secrets; print(secrets.token_hex(32))")
    DB_PATH      — path to the SQLite database (default: ./sumo.db)
    PORT         — port to run the app on (default: 8080)
"""

import os, sys
from dotenv import load_dotenv

load_dotenv()  # reads .env if present, does nothing when hosting


def get_secret_key() -> str:
    key = os.environ.get('SECRET_KEY')
    if not key:
        sys.exit("SECRET_KEY environment variable not set. See .env.example")
    return key


DB_PATH = os.environ.get('DB_PATH', './sumo.db')
PORT    = int(os.environ.get('PORT', 8080))

