from rich.table import Table
import asyncio
from rich.console import Console
from client_app.apicalls import api_get_leaderboard, api_get_match_history
import questionary
from datetime import datetime
from rich.table import Table
from rich.text import Text
from rich import box

class UserState:
    """Contiene lo stato globale dell'utente loggato."""
    def __init__(self):
        self.token = None
        self.username = None

def schermata_leaderboard(console: Console, CURRENT_USER_STATE: UserState):
    """Menu principale per Classifiche e Storico Partite."""
    
    while True:
        console.clear()
        console.print("[bold blue]--- STATISTICHE & CLASSIFICHE ---[/]")
        
        scelta_menu = questionary.select(
            "Cosa vuoi visualizzare?",
            choices=[
                "Global Leaderboard",
                "My Match History",
                "Indietro"
            ]
        ).ask()

        if scelta_menu == "Global Leaderboard":
            _visualizza_leaderboard(console, CURRENT_USER_STATE)
            
        elif scelta_menu == "My Match History":
            _visualizza_storico(console, CURRENT_USER_STATE)
            
        elif scelta_menu == "Indietro" or scelta_menu is None:
            break

# --- SOTTO-FUNZIONE: LEADERBOARD PAGINATA ---

# Costante per facilitare modifiche future
ITEMS_PER_PAGE = 10

def _visualizza_leaderboard(console: Console, state: UserState):
    SELECTED_PAGE = 0  # Pagina interna (0 = Pagina 1 visualizzata)
    
    while True:
        console.clear()
        # Mostriamo +1 per l'utente, così vede "Page 1" invece di "Page 0"
        console.print(f"[bold blue]--- GLOBAL LEADERBOARD (Page {SELECTED_PAGE + 1}) ---[/]")
        
        # Chiamata API (passiamo l'indice 0-based)
        result = asyncio.run(api_get_leaderboard(SELECTED_PAGE, CURRENT_USER_STATE=state))
        
        if result:
            table = Table(title=f"Page {SELECTED_PAGE + 1}", style="magenta")
            table.add_column("Rank", justify="right", style="cyan", no_wrap=True)
            table.add_column("Username", style="white")
            table.add_column("Wins", justify="right", style="green")
            table.add_column("Losses", justify="right", style="red")

            # --- CORREZIONE QUI ---
            # Se siamo a pagina 0: (0 * 10) + 1 = 1
            # Se siamo a pagina 1: (1 * 10) + 1 = 11
            start_rank = (SELECTED_PAGE * ITEMS_PER_PAGE) + 1
            
            for idx, entry in enumerate(result):
                rank = str(start_rank + idx)
                user = str(entry.get('username', 'Unknown'))
                wins = str(entry.get('wins', 0))
                loss = str(entry.get('losses', 0))
                table.add_row(rank, user, wins, loss)

            console.print(table)
        else:
            console.print(f"\n[italic red]Nessun giocatore trovato a pagina {SELECTED_PAGE + 1}.[/]")

        # Menu di Navigazione
        console.print("") 
        nav_choices = ["-> Next Page"]
        
        if SELECTED_PAGE > 0:
            nav_choices.insert(0, "<- Prev Page")
        
        nav_choices.append("Go to Page...")
        nav_choices.append("Back to Menu")

        scelta = questionary.select(
            "Naviga:",
            choices=nav_choices
        ).ask()

        if scelta == "<- Prev Page":
            SELECTED_PAGE -= 1
        elif scelta == "-> Next Page":
            SELECTED_PAGE += 1
        elif scelta == "Go to Page...":
            num = questionary.text("Inserisci numero pagina:").ask()
            # Corretto: se l'utente scrive "1", internamente diventa 0
            if num.isdigit() and int(num) > 0:
                SELECTED_PAGE = int(num) - 1 
        elif scelta == "Back to Menu" or scelta is None:
            break
# --- SOTTO-FUNZIONE: STORICO PARTITE ---


# Funzione helper per convertire "K of diamonds" in "K ♦️"
def _parse_card_text(card_text):
    if not card_text or card_text == "None": return ""
    if "JOKER" in card_text: return "🃏"
    
    parts = card_text.split(" of ")
    if len(parts) != 2: return card_text
    
    val, suit = parts[0], parts[1].lower()
    suit_map = {
        'hearts': '❤️', 'diamonds': '♦️', 
        'clubs': '♣️', 'spades': '♠️', 'none': ''
    }
    return f"{val} {suit_map.get(suit, '')}"

def _visualizza_storico(console: Console, state: UserState):
    console.clear()
    console.print("[bold blue]--- 📜 MY MATCH HISTORY ---[/]")
    console.print("Caricamento partite...")

    # Chiamata API
    history_list = asyncio.run(api_get_match_history(state))

    if not history_list:
        console.print("\n[italic yellow]Non hai ancora giocato nessuna partita.[/]")
        questionary.text("Premi Invio per tornare indietro...").ask()
        return

    # Creazione Tabella Fancy
    table = Table(
        title=f"Storico Partite di {state.username}", 
        box=box.ROUNDED,
        header_style="bold cyan",
        expand=True
    )

    table.add_column("Date", style="dim", width=12)
    table.add_column("Opponent", style="white")
    table.add_column("Result", justify="center")
    table.add_column("Score", justify="center")
    table.add_column("Timeline (Turni)", justify="left") 

    for match in history_list:
        # 1. Parsing Dati Base
        my_username = state.username
        
        # Identifica chi è Player 1 e Player 2
        p1_name = match.get('player1')
        p2_name = match.get('player2')
        
        # Identifica l'avversario
        is_p1 = (my_username == p1_name)
        opponent = p2_name if is_p1 else p1_name
        
        # Punteggi
        score1 = match.get('points1', 0)
        score2 = match.get('points2', 0)
        my_score = score1 if is_p1 else score2
        opp_score = score2 if is_p1 else score1
        score_str = f"{my_score} - {opp_score}"

        # 2. Determinare Vincitore
        winner_code = match.get('winner') # '1' o '2'
        
        am_i_winner = False
        if (is_p1 and winner_code == '1') or (not is_p1 and winner_code == '2'):
            am_i_winner = True
            
        # Badge Risultato
        if am_i_winner:
            res_badge = "[bold white on green] WIN [/]"
        elif winner_code == '0': # Pareggio (se gestito)
            res_badge = "[bold black on yellow] DRAW [/]"
        else:
            res_badge = "[bold white on red] LOSS [/]"

        # 3. Formattazione Data
        started_at = match.get('started_at')
        date_str = "N/A"
        if started_at:
            try:
                # Parsa la stringa ISO (es. 2025-12-16T19:47:57.816527)
                dt_obj = datetime.fromisoformat(started_at)
                date_str = dt_obj.strftime("%d/%m %H:%M")
            except:
                pass

        # 4. Creazione Timeline Turni (Fancy!)
        # Analizziamo il log per vedere chi ha vinto ogni singolo turno
        log = match.get('log', [])
        timeline_dots = ""
        
        for turn in log:
            turn_winner = turn.get('winner') # Qui ritorna lo username es 'aa'
            
            if turn_winner == my_username:
                timeline_dots += "🟢" # Ho vinto io il turno
            elif turn_winner == opponent:
                timeline_dots += "🔴" # Ha vinto lui
            else:
                timeline_dots += "⚪" # Pareggio o nessuno
        
        # Aggiungiamo riga alla tabella
        table.add_row(date_str, opponent, res_badge, score_str, timeline_dots)

    console.print(table)
    console.print("\n[dim]Legenda Timeline: 🟢=Tuo Turno Vinto, 🔴=Turno Perso[/]")
    console.print("\n")
    
    # Opzionale: Visualizzare dettagli di una partita specifica?
    questionary.text("Premi Invio per tornare al menu...").ask()