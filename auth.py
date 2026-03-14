"""
auth.py — password setup, login verification, and session management.

First-time setup:
    python auth.py (Setup all users passwords)

Passwords are bcrypt-hashed and stored in auth_config.json (NEVER plaintext, plaintext bad)
Sessions are random tokens stored server-side in sumo.db
"""

import sys, json, os, sqlite3, secrets, time, getpass
import bcrypt
from config import get_auth_config, DB_PATH


SESSION_KEY     = 'sumo_session'   # key used in app.storage.user
SESSION_DAYS    = 7
MAX_FAILURES    = 5
LOCKOUT_MINUTES = 15
PLAYERS         = ['Ted', 'Kevin', 'Jamie', 'Mike']


# Interactive CLI wizard - run to create/update passwords
def setup():
    raw = os.environ.get('AUTH_CONFIG')
    config = json.loads(raw) if raw else {}

    config.setdefault('secret_key', secrets.token_hex(32))
    config.setdefault('users', {})

    print("\n=== Sumo Fantasy: Password Setup ===\n")
    for player in PLAYERS:
        if player in config['users']:
            if input(f"  {player} already set. Reset? (y/N): ").lower() != 'y':
                continue

        while True:
            pw = getpass.getpass(f"  Password for {player}: ")

            if pw != getpass.getpass("  Confirm: "):
                print("  Passwords didn't match.\n")
                continue

            if len(pw) < 8:
                print("  Need at least 8 characters.\n")
                continue

            config['users'][player] = bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()
            print(f"  ✓ Set\n")
            break

    # Writes Auth config into .env file
    config_json = json.dumps(config)

    env_path = '.env'
    lines = []

    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = [l for l in f.readlines() if not l.startswith('AUTH_CONFIG=')]

    lines.append(f"AUTH_CONFIG={config_json}\n")

    with open(env_path, 'w') as f:
        f.writelines(lines)

    if sys.platform != 'win32':
        os.chmod(env_path, 0o600)

    print(f"AUTH_CONFIG has been set")


# Create DB auth tables (called from main.py's init_db)
def init_auth_tables(cursor):
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        token     TEXT PRIMARY KEY,
        player    TEXT NOT NULL,
        last_seen REAL NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS login_attempts (
        ip           TEXT PRIMARY KEY,
        fail_count   INTEGER DEFAULT 0,
        locked_until REAL
    )
    ''')


# Login Returns (True, player_name) on success or (False, error_message) on failure
def verify_login(player: str, password: str, ip: str) -> tuple[bool, str]:
    config = get_auth_config()

    # Check rate limit
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT fail_count, locked_until FROM login_attempts WHERE ip=?", (ip,)).fetchone()

    # Enforce rate limiting
    if row and row[1] and time.time() < row[1]:
        conn.close()
        return False, f"Too many attempts. Try again in {int(row[1]-time.time())//60+1} min."

    # Find canonical (real) username, fall back to dummy hash
    users = config['users']
    canonical = next((p for p in users if p.lower() == player.lower()), None)
    stored = users.get(canonical, '$2b$12$invalidhashpaddinginvalidhashpaddinginvalidhash00000')

    # Always run bcrypt — prevents timing attacks by using a dummy hash
    ok = False
    try:
        ok = bcrypt.checkpw(password.encode(), stored.encode())
    except Exception:
        pass

    # Remove login_attempts when sign-in successfull
    if ok and canonical:
        conn.execute("DELETE FROM login_attempts WHERE ip=?", (ip,))
        conn.commit()
        conn.close()
        return True, canonical

    # Record failure and lock out if beyond maximum attempts
    count = (row[0] if row else 0) + 1
    locked = (time.time() + LOCKOUT_MINUTES * 60) if count >= MAX_FAILURES else None

    # Upsert operation for the rate limiter
    conn.execute('''
                    INSERT INTO login_attempts (ip, fail_count, locked_until) VALUES (?,?,?)
                    ON CONFLICT(ip) DO UPDATE SET
                    fail_count=excluded.fail_count,
                    locked_until=excluded.locked_until
                 ''',
                 (ip, count, locked))

    conn.commit()
    conn.close()

    return False, "Invalid username or password."


# Sessions
def create_session(player: str) -> str:
    token = secrets.token_hex(32)
    conn = sqlite3.connect(DB_PATH)

    conn.execute("INSERT INTO sessions (token, player, last_seen) VALUES (?,?,?)", (token, player, time.time()))

    conn.commit()
    conn.close()
    return token


# Returns player name if valid, else None
def validate_session(token) -> str | None:
    if not token:
        return None

    cutoff = time.time() - SESSION_DAYS * 86400
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT player FROM sessions WHERE token=? AND last_seen>?", (token, cutoff)).fetchone()

    if row:
        conn.execute("UPDATE sessions SET last_seen=? WHERE token=?", (time.time(), token))
        conn.commit()

    conn.close()

    return row[0] if row else None


# Remove a session by deleting it's DB entry
def revoke_session(token: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
    conn.close()


# Entry point for password setup
if __name__ == '__main__':
    setup()
