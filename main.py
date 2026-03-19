"""
Fantasy Sumo League

Setup:
    pip install nicegui bcrypt requests
    python auth.py       set/update passwords
    python main.py       run the app
"""

import asyncio, sqlite3
import requests
from nicegui import ui, app
from fastapi import Request
from fastapi.responses import RedirectResponse

import auth
from config import DB_PATH, PORT, get_secret_key


# --- DATABASE SETUP (Standard SQLite) ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS wrestlers (
        id             INTEGER PRIMARY KEY,
        name           TEXT,
        rank           TEXT,
        current_wins   INT,
        current_losses INT,
        owner          TEXT
    )''')
    auth.init_auth_tables(c)   # adds sessions + login_attempts tables

    conn.commit()
    conn.close()

def init_results_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Stores each match result: Day, Wrestler, Opponent, and Result (win/loss)
    cursor.execute('''CREATE TABLE IF NOT EXISTS daily_results 
                      (id INTEGER PRIMARY KEY, 
                       basho_id TEXT,
                       day INTEGER,
                       rikishi_name TEXT,
                       opponent_name TEXT,
                       result TEXT,
                       kimarite TEXT)''')
    conn.commit()
    conn.close()

def menu():
    with ui.header().classes('items-center justify-between bg-indigo-9'):
        with ui.row().classes('items-center'):
            ui.label('Fantasy Sumo').classes('text-xl font-bold')
        
        with ui.row():
            ui.button('Draft Board', on_click=lambda: ui.navigate.to('/')).props('flat color=white icon=groups')
            ui.button('Results', on_click=lambda: ui.navigate.to('/results')).props('flat color=white icon=trending_up')    

@app.on_startup
def startup():
    # Call all your table creation functions here
    init_db()         # For wrestlers
    init_results_db() # For the new daily_results table
    print("Database tables verified and ready.")


# Auth middleware — redirects unauthenticated requests to /login
@app.middleware('http')
async def gate(request: Request, call_next):
    public = ('/login', '/_nicegui', '/favicon')

    if any(request.url.path.startswith(p) for p in public):
        return await call_next(request)

    if not auth.validate_session(app.storage.user.get(auth.SESSION_KEY)):
        return RedirectResponse('/login', status_code=303)

    return await call_next(request)


# Login page
@ui.page('/login')
async def login_page(request: Request):
    # Redirect to app if user session is validated
    if auth.validate_session(app.storage.user.get(auth.SESSION_KEY)):
        ui.navigate.to('/')
        return

    # Works when client is behind proxy
    client_ip = request.headers.get('x-forwarded-for', request.client.host).split(',')[0].strip()

    # Login page content
    with ui.column().classes('absolute-center items-center gap-4').style('width: 320px'):
        ui.label('Fantasy Sumo League').classes('text-h5 text-bold text-center')
        ui.label('March 2026 · Members Only').classes('text-caption text-grey-6 text-center')
        ui.separator()
        name_input = ui.input(label='Your name').classes('w-full')
        pw_input   = ui.input(label='Password', password=True, password_toggle_button=True).classes('w-full')
        error_msg  = ui.label('').classes('text-negative text-caption')

        async def do_login():
            error_msg.text = ''
            if not name_input.value:
                error_msg.text = 'Please select your name.'
                return

            # Run bcrypt in a thread - it's intentionally slow and would block the UI otherwise
            # Wrapped in a lamba to be an zero-arguement callable for `run_in_executor`
            ok, result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: auth.verify_login(name_input.value, pw_input.value or '', client_ip)
            )

            if ok:
                app.storage.user[auth.SESSION_KEY] = auth.create_session(result)
                app.storage.user['player'] = result
                ui.navigate.to('/')
            else:
                error_msg.text = result
                pw_input.value = ''

        pw_input.on('keydown.enter', do_login)
        name_input.on('keydown.enter', do_login)
        ui.button('Sign In', on_click=do_login).classes('w-full').props('unelevated color=primary')

async def update_all_available_days():
    # Since it's March 19 in Dublin, it's already March 20 (Day 6) in Osaka.
    # We loop through all potential days of the tournament.
    for d in range(1, 16):
        await update_daily_results(d)
    ui.notify("Tournament history updated!", color='green')
    ui.navigate.to('/results') # Refresh page to show new data

    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: requests.get(url, timeout=5)
        )
        if response.status_code == 200:
            data = response.json()
            all_rikishi = data.get("east", []) + data.get("west", [])
            
            conn = sqlite3.connect('DB_PATH')
            cursor = conn.cursor()
            
            for r in all_rikishi:
                name = r.get("shikonaEn")
                # Look at the specific day in their record list
                # Day 1 is index 0, Day 2 is index 1, etc.
                record = r.get("record", [])
                if len(record) >= day_number:
                    match = record[day_number - 1]
                    res = match.get("result") # "win" or "loss"
                    opp = match.get("opponentShikonaEn")
                    kim = match.get("kimarite")

                    if res: # Only save if the match has actually happened
                        cursor.execute("""
                            INSERT OR REPLACE INTO daily_results 
                            (basho_id, day, rikishi_name, opponent_name, result, kimarite)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, ("202603", day_number, name, opp, res, kim))
            
            conn.commit()
            conn.close()
            ui.notify(f'Day {day_number} results updated!', type='positive')
    except Exception as e:
        ui.notify(f'Update failed: {e}')

# Main app
wrestler_grid  = None

@ui.page('/')
def index():
    menu()
    global wrestler_grid

    logged_in_player = app.storage.user.get('player')
    if not logged_in_player:   # middleware handles HTTP, this covers WebSocket
        ui.navigate.to('/login')
        return

    def do_logout():
        auth.revoke_session(app.storage.user.get(auth.SESSION_KEY))
        app.storage.user.clear()
        ui.navigate.to('/login')

    # Header
    with ui.row().classes('items-center justify-between w-full q-pa-md'):
        ui.label('Fantasy Sumo League').classes('text-h3 q-ma-md')
        with ui.row().classes('items-center gap-2'):
            ui.label(f'👤 {logged_in_player}').classes('text-bold')
            ui.button('Sign Out', on_click=do_logout).props('flat color=negative')

    # Controls
    with ui.row().classes('items-center q-pa-md bg-grey-2 w-full'):
        ui.label('Drafting for:').classes('text-bold')
        ui.label(logged_in_player).classes('text-bold')
        ui.button('Update Banzuke', on_click=seed_data).props('icon=refresh color=green')
        ui.label('March 2026 Basho').classes('ml-auto text-italic')

    ui.separator()
    wrestler_grid = ui.grid(columns=4).classes('w-full q-pa-md')
    refresh_list()

@ui.page('/results')
def results_page():
    menu()
    
    with ui.row().classes('w-full items-center justify-between q-pa-md'):
        ui.label('March 2026 Basho History').classes('text-h4')
        # Button to sync the latest data (Day 5/6)
        ui.button('Sync Latest', on_click=lambda: update_all_available_days()).props('icon=sync')

    conn = sqlite3.connect('DB_PATH')
    cursor = conn.cursor()
    
    # 1. Find the highest day we have data for
    cursor.execute("SELECT MAX(day) FROM daily_results")
    max_day = cursor.fetchone()[0] or 0
    
    if max_day == 0:
        ui.label('No results found. Click Sync to fetch data!').classes('q-pa-lg text-h6 text-grey')
        conn.close()
        return

    # 2. Loop from current day down to Day 1
    for day_num in range(max_day, 0, -1):
        with ui.expansion(f'Day {day_num} Results', icon='calendar_today').classes('w-full mb-2'):
            
            # Fetch results specifically for THIS day
            cursor.execute("""
                SELECT r.rikishi_name, r.result, w.owner, r.opponent_name, r.kimarite
                FROM daily_results r
                LEFT JOIN wrestlers w ON r.rikishi_name = w.name
                WHERE r.day = ?
                ORDER BY r.result DESC, r.rikishi_name ASC
            """, (day_num,))
            
            day_rows = [dict(zip(['rikishi', 'res', 'owner', 'opp', 'kim'], row)) for row in cursor.fetchall()]
            
            # Define columns for this specific day's table
            columns = [
                {'name': 'rikishi', 'label': 'Rikishi', 'field': 'rikishi'},
                {'name': 'owner', 'label': 'Owner', 'field': 'owner'},
                {'name': 'res', 'label': 'Result', 'field': 'res'},
                {'name': 'opp', 'label': 'Opponent', 'field': 'opp'},
            ]
            
            ui.table(columns=columns, rows=day_rows).classes('w-full').props('flat bordered')

    conn.close()


async def seed_data():
    url = "https://www.sumo-api.com/api/basho/202603/banzuke/Makuuchi"
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: http.get(url, timeout=5)
        )
        if response.status_code == 200:
            data = response.json()
            all_rikishi = data.get("east", []) + data.get("west", [])
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            for r in all_rikishi:
                cursor.execute(
                    "INSERT OR REPLACE INTO wrestlers (name, rank, current_wins, current_losses, owner) VALUES (?,?,?,?,?)",
                    (r.get("shikonaEn"), r.get("rank"), r.get("wins", 0), r.get("losses", 0), None)
                )
            conn.commit()
            conn.close()
            ui.notify(f'Banzuke Updated: {len(all_rikishi)} rikishi synced!')
            refresh_list()
    except Exception as e:
        ui.notify(f'Error: {e}')


# Draft a wrestler with the currently logged in player
def draft_wrestler(wrestler_name):
    player = app.storage.user.get('player')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT owner FROM wrestlers WHERE name = ?", (wrestler_name,))
    row = cursor.fetchone()

    if row and row[0]:
        ui.notify(f'{wrestler_name} is already taken by {row[0]}!', type='negative')
    else:
        cursor.execute("UPDATE wrestlers SET owner = ? WHERE name = ?", (player, wrestler_name))
        conn.commit()
        ui.notify(f'you drafted {wrestler_name}!', color='green')
        refresh_list()

    conn.close()


def refresh_list():
    global wrestler_grid

    if wrestler_grid is None:
        return

    wrestler_grid.clear()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, rank, owner FROM wrestlers")
    rows = cursor.fetchall()
    conn.close()

    with wrestler_grid:
        for name, rank, owner in rows:
            with ui.card():
                ui.label(name).classes('text-bold')
                ui.label(rank or '').classes('text-caption text-grey-6')
                if owner:
                    ui.badge(owner, color='green')
                else:
                    ui.button(
                        'Draft',
                        on_click=lambda n=name: draft_wrestler(n)
                    ).props('dense unelevated color=primary size=sm')

# Run
ui.run(
    host='0.0.0.0',
    port=PORT,
    title='Fantasy Sumo League',
    storage_secret=get_secret_key(),
)