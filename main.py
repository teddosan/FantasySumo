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

def draft_wrestler(wrestler_name):
    # Get the player selected in the dropdown
    player_name = current_picker.value
    
    if not player_name:
        ui.notify('Select a drafter first!', type='warning')
        return

    conn = sqlite3.connect('sumo.db')
    cursor = conn.cursor()
    
    # Check if someone else already drafted them
    cursor.execute("SELECT owner FROM wrestlers WHERE name = ?", (wrestler_name,))
    result = cursor.fetchone()
    
    if result and result[0]:
        ui.notify(f'{wrestler_name} is already owned by {result[0]}!', type='negative')
    else:
        # Assign the wrestler to the player
        cursor.execute("UPDATE wrestlers SET owner = ? WHERE name = ?", (player_name, wrestler_name))
        conn.commit()
        ui.notify(f'{player_name} drafted {wrestler_name}!', color='green')
        # Refresh the UI to reflect the change
        refresh_list()
    
    conn.close()

def release_wrestler(wrestler_name):
    conn = sqlite3.connect('sumo.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE wrestlers SET owner = NULL WHERE name = ?", (wrestler_name,))
    conn.commit()
    conn.close()
    refresh_list()

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
            # Highlight owned cards in gray, available in white
            card_classes = 'w-64 bg-gray-100' if owner else 'w-64 bg-white shadow-lg'
            # ... your card building code ...
            with ui.card().classes(card_classes):
                with ui.card_section():
                    ui.label(name).classes('text-h6')
                    ui.label(rank).classes('text-subtitle2 text-grey')
                    
                    if owner:
                        ui.label(f'DRAFTED BY: {owner}').classes('text-orange text-bold q-mt-sm')
                
                with ui.card_actions():
                    if not owner:
                        # The button passes the specific wrestler name to our function
                        ui.button('Draft', on_click=lambda n=name: draft_wrestler(n)).props('flat color=primary')
                    else:
                        # Optional: Add a 'Release' button for the commissioner (you)
                        ui.button('Release', on_click=lambda n=name: release_wrestler(n)).props('flat color=red')

ui.run(title='Sumo Fantasy')




