from nicegui import ui
import requests
import sqlite3
import asyncio

players = ['Ted', 'Kevin', 'Jamie', 'Mike']
wrestler_grid = None
current_picker = None

# --- DATABASE SETUP (Standard SQLite) ---
def init_db():
    conn = sqlite3.connect('sumo.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS wrestlers 
                      (id INTEGER PRIMARY KEY, name TEXT, rank TEXT, current_wins INT, current_losses INT, owner TEXT)''')
    conn.commit()
    conn.close()

init_db()
   
async def seed_data():
    url = "https://www.sumo-api.com/api/basho/202603/banzuke/Makuuchi"
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: requests.get(url, timeout=5)
        )
        if response.status_code == 200:
            data = response.json()
            
            # Combine both East and West lists
            all_rikishi = data.get("east", []) + data.get("west", [])
            
            conn = sqlite3.connect('sumo.db')
            cursor = conn.cursor()
            
            for r in all_rikishi:
                name = r.get("shikonaEn")
                rank = r.get("rank")
                # We can even store their current wins/losses!
                wins = r.get("wins", 0)
                losses = r.get("losses", 0)
                owner = None

                cursor.execute("""
                    INSERT OR REPLACE INTO wrestlers (name, rank, current_wins, current_losses, owner) 
                    VALUES (?, ?, ?, ?, ?)
                """, (name, rank, wins, losses, owner))
            
            conn.commit()
            conn.close()
            ui.notify(f'Banzuke Updated: {len(all_rikishi)} rikishi synced!')
            refresh_list()
    except Exception as e:
        ui.notify(f'Error: {e}')


# --- UI: The Main Page ---
@ui.page('/')

def index():
    global current_picker, wrestler_grid, players
    
    # 1. Page Header
    ui.label('Fantasy Sumo League').classes('text-h3 q-ma-md')
    
    # 2. Controls Row (Picker + Update Button)
    with ui.row().classes('items-center q-pa-md bg-grey-2 w-full'):
        ui.label('Drafting for:').classes('text-bold')
        current_picker = ui.select(
            options=players,
            value='Ted'
        ).classes('w-48')
        
        # Add the missing button here
        ui.button('Update Banzuke', on_click=seed_data).props('icon=refresh color=green')
        
        ui.label('March 2026 Basho').classes('ml-auto text-italic')

    ui.separator()

    # 3. Create the Grid (Crucial: Must be created before refresh_list is called)
    wrestler_grid = ui.grid(columns=4).classes('w-full q-pa-md')
    
    # 4. Fill the grid with data
    refresh_list()

def draft_wrestler(wrestler_name, player_name):
    if not player_name:
        ui.notify('Please select a drafter first!', type='warning')
        return

    conn = sqlite3.connect('sumo.db')
    cursor = conn.cursor()
    
    # Check if already drafted
    cursor.execute("SELECT owner FROM wrestlers WHERE name = ?", (wrestler_name,))
    row = cursor.fetchone()
    
    if row and row[0]:
        ui.notify(f'{wrestler_name} is already taken by {row[0]}!', type='negative')
    else:
        cursor.execute("UPDATE wrestlers SET owner = ? WHERE name = ?", (player_name, wrestler_name))
        conn.commit()
        ui.notify(f'{player_name} drafted {wrestler_name}!', color='green')
        refresh_list() # Redraw the UI to show the new owner
    
    conn.close()

def refresh_list():
    global wrestler_grid
    
    # SAFETY GUARD: If the page hasn't finished loading the grid, stop here.
    if wrestler_grid is None:
        return
        
    wrestler_grid.clear()
    
    conn = sqlite3.connect('sumo.db')
    cursor = conn.cursor()
    # Make sure your SELECT matches your table columns!
    cursor.execute("SELECT name, rank, owner FROM wrestlers")
    rows = cursor.fetchall()
    conn.close()

    with wrestler_grid:
        for name, rank, owner in rows:
            # ... your card building code ...
            with ui.card():
                ui.label(name)
                # etc.

ui.run(title='Sumo Fantasy')




