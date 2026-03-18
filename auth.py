"""
auth.py — password setup, login verification, and session management.

Manage players:
    python auth.py

Passwords are bcrypt-hashed and stored in the database players table (never plaintext).
Sessions are random tokens stored server-side in sumo.db.
"""

import sys, os, sqlite3, secrets, time, getpass, logging
import bcrypt
from config import DB_PATH


SESSION_KEY     = 'sumo_session'
SESSION_DAYS    = 7
MAX_FAILURES    = 5
LOCKOUT_MINUTES = 15


# Logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    filename='logs/auth.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
log = logging.getLogger(__name__)


# DB tables
def init_auth_tables(cursor):
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            username      TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            token     TEXT PRIMARY KEY,
            player    TEXT NOT NULL,
            last_seen REAL NOT NULL
        )
    ''')
    # Rate limiting keyed on (ip, username) — covers proxy attacks targeting a specific account
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS login_attempts (
            ip           TEXT,
            username     TEXT,
            fail_count   INTEGER DEFAULT 0,
            locked_until REAL,
            PRIMARY KEY (ip, username)
        )
    ''')


# Player helpers
def _get_players() -> dict:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT username, password_hash FROM players").fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}

def _find_player(name: str) -> str | None:
    # Case-insensitive lookup
    return next((p for p in _get_players() if p.lower() == name.lower()), None)

def _upsert_player(username: str, password_hash: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        INSERT INTO players (username, password_hash) VALUES (?, ?)
        ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash
    ''', (username, password_hash))
    conn.commit()
    conn.close()

def _delete_player(username: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM players WHERE username=?", (username,))
    conn.execute("DELETE FROM sessions WHERE player=?", (username,))
    conn.commit()
    conn.close()

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


# Login
def verify_login(player: str, password: str, ip: str) -> tuple[bool, str]:
    """Returns (True, player_name) on success or (False, error_message) on failure."""
    conn = sqlite3.connect(DB_PATH)

    # Check rate limit by (ip, username) combined
    row = conn.execute(
        "SELECT fail_count, locked_until FROM login_attempts WHERE ip=? AND username=?",
        (ip, player.lower())
    ).fetchone()

    if row and row[1] and time.time() < row[1]:
        conn.close()
        mins = int(row[1] - time.time()) // 60 + 1
        log.warning(f"Blocked login for '{player}' from {ip} — still locked for {mins} min")
        return False, f"Too many attempts. Try again in {mins} min."

    # Find canonical player name (case-insensitive), fall back to dummy hash
    players  = _get_players()
    canonical = next((p for p in players if p.lower() == player.lower()), None)
    stored    = players.get(canonical, '$2b$12$invalidhashpaddinginvalidhashpaddinginvalidhash00000')

    # Always run bcrypt — prevents timing attacks that reveal valid player names
    ok = False
    try:
        ok = bcrypt.checkpw(password.encode(), stored.encode())
    except Exception:
        pass

    if ok and canonical:
        conn.execute(
            "DELETE FROM login_attempts WHERE ip=? AND username=?",
            (ip, player.lower())
        )
        conn.commit()
        conn.close()
        log.info(f"Successful login for '{canonical}' from {ip}")
        return True, canonical

    # Record failure, lock out if at limit
    count  = (row[0] if row else 0) + 1
    locked = (time.time() + LOCKOUT_MINUTES * 60) if count >= MAX_FAILURES else None

    conn.execute('''
        INSERT INTO login_attempts (ip, username, fail_count, locked_until) VALUES (?,?,?,?)
        ON CONFLICT(ip, username) DO UPDATE SET
        fail_count=excluded.fail_count,
        locked_until=excluded.locked_until
    ''', (ip, player.lower(), count, locked))
    conn.commit()
    conn.close()

    if locked:
        log.warning(f"Player '{player}' from {ip} locked out after {count} failures")
    else:
        log.warning(f"Failed login for '{player}' from {ip} ({count}/{MAX_FAILURES})")

    return False, "Invalid username or password."


# Revokes all existing sessions for this player then issues a new token
def create_session(player: str) -> str:
    token = secrets.token_hex(32)
    conn  = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM sessions WHERE player=?", (player,))
    conn.execute(
        "INSERT INTO sessions (token, player, last_seen) VALUES (?,?,?)",
        (token, player, time.time())
    )
    conn.commit()
    conn.close()
    log.info(f"Session created for '{player}'")
    return token


# Returns player name if session is valid, else None
def validate_session(token) -> str | None:
    if not token:
        return None
    cutoff = time.time() - SESSION_DAYS * 86400
    conn   = sqlite3.connect(DB_PATH)
    row    = conn.execute(
        "SELECT player FROM sessions WHERE token=? AND last_seen>?", (token, cutoff)
    ).fetchone()
    if row:
        conn.execute("UPDATE sessions SET last_seen=? WHERE token=?", (time.time(), token))
        conn.commit()
    conn.close()
    return row[0] if row else None


# Delete session from DB (immediate lockout)
def revoke_session(token: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
    conn.close()
    log.info("Session revoked")


# CLI: Player management
def manage_players():
    # Ensure DB tables exist before read/write
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    init_auth_tables(c)
    conn.commit()
    conn.close()

    # Generate SECRET_KEY if not already set
    if not os.environ.get('SECRET_KEY'):
        key = secrets.token_hex(32)
        env_path = '.env'
        with open(env_path, 'a') as f:
            f.write(f"SECRET_KEY={key}\n")
        if sys.platform != 'win32':
            os.chmod(env_path, 0o600)
        print(f"\nGenerated SECRET_KEY and saved to .env\n")

    while True:
        os.system('cls' if sys.platform == 'win32' else 'clear')
        print("== Fantasy Sumo: Player Management ==\n")
        print("  a) Add player")
        print("  m) Modify player password")
        print("  d) Delete player")
        print("  l) List players")
        print("  q) Quit\n")

        match input("  Choice: ").strip().lower():

            case 'a':
                name = input("  Player name: ").strip()
                if not name:
                    print("  Player name cannot be empty.")
                elif _find_player(name):
                    print(f"  A player named '{name}' already exists. Use modify to change their password.")
                else:
                    pw = _get_password()
                    if pw:
                        _upsert_player(name, _hash_password(pw))
                        print(f"  {name} added.")
                input("\n  Press Enter to continue...")

            case 'm':
                name = input("  Player name to modify: ").strip()
                canonical = _find_player(name)
                if not canonical:
                    print(f"  No player named '{name}' found.")
                else:
                    pw = _get_password()
                    if pw:
                        _upsert_player(canonical, _hash_password(pw))
                        print(f"  Password updated for {canonical}.")
                input("\n  Press Enter to continue...")

            case 'd':
                name = input("  Player name to delete: ").strip()
                canonical = _find_player(name)
                if not canonical:
                    print(f"  No player named '{name}' found.")
                else:
                    confirm = input(f"  Delete {canonical}? This cannot be undone. (y/N): ").strip().lower()
                    if confirm == 'y':
                        _delete_player(canonical)
                        print(f"  {canonical} deleted and sessions revoked.")
                input("\n  Press Enter to continue...")

            case 'l':
                players = _get_players()
                if players:
                    print()
                    for i, name in enumerate(players, 1):
                        print(f"  {i}. {name}")
                else:
                    print("  No players set up yet.")
                input("\n  Press Enter to continue...")

            case 'q':
                break

            case _:
                print("  Invalid choice.")
                input("\n  Press Enter to continue...")


# Password prompt
def _get_password() -> str | None:
    while True:
        pw = getpass.getpass("  Password: ")
        if len(pw) < 8:
            print("  Need at least 8 characters."); continue
        if pw != getpass.getpass("  Confirm: "):
            print("  Passwords did not match."); continue
        return pw


# Entry point
if __name__ == '__main__':
    manage_players()
