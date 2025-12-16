from rich.table import Table
import asyncio
from rich.console import Console
from client_app.apicalls import api_get_leaderboard, api_get_match_history
import questionary

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
                "🏆 Global Leaderboard",
                "📜 My Match History",
                "🔙 Indietro"
            ]
        ).ask()

        if scelta_menu == "🏆 Global Leaderboard":
            _visualizza_leaderboard(console, CURRENT_USER_STATE)
            
        elif scelta_menu == "📜 My Match History":
            _visualizza_storico(console, CURRENT_USER_STATE)
            
        elif scelta_menu == "🔙 Indietro" or scelta_menu is None:
            break

# --- SOTTO-FUNZIONE: LEADERBOARD PAGINATA ---
def _visualizza_leaderboard(console: Console, state: UserState):
    SELECTED_PAGE = 1
    
    while True:
        console.clear()
        console.print(f"[bold blue]--- GLOBAL LEADERBOARD (Page {SELECTED_PAGE}) ---[/]")
        
        # Chiamata API
        result = asyncio.run(api_get_leaderboard(SELECTED_PAGE, CURRENT_USER_STATE=state))
        
        if result:
            # Creiamo una tabella bella da vedere
            table = Table(title=f"Page {SELECTED_PAGE}", style="magenta")
            table.add_column("Rank", justify="right", style="cyan", no_wrap=True)
            table.add_column("Username", style="white")
            table.add_column("Wins", justify="right", style="green")
            table.add_column("Losses", justify="right", style="red")

            # Calcolo del rank assoluto in base alla pagina (assumendo 10 item per pagina)
            start_rank = 1 + (SELECTED_PAGE - 1) * 10
            
            for idx, entry in enumerate(result):
                rank = str(start_rank + idx)
                user = str(entry.get('username', 'Unknown'))
                wins = str(entry.get('wins', 0))
                loss = str(entry.get('losses', 0))
                table.add_row(rank, user, wins, loss)

            console.print(table)
        else:
            console.print(f"\n[italic red]Nessun giocatore trovato a pagina {SELECTED_PAGE}.[/]")

        # Menu di Navigazione
        console.print("") # Spazio vuoto
        nav_choices = ["-> Next Page"]
        
        if SELECTED_PAGE > 1:
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
            if num.isdigit() and int(num) > 0:
                SELECTED_PAGE = int(num)
        elif scelta == "Back to Menu" or scelta is None:
            break

# --- SOTTO-FUNZIONE: STORICO PARTITE ---
def _visualizza_storico(console: Console, state: UserState):
    console.clear()
    console.print("[bold blue]--- MY MATCH HISTORY ---[/]")
    console.print("Caricamento storico...")

    # Chiamata API
    history = asyncio.run(api_get_match_history(state))
    print(history)
    if not history:
        console.print("[italic yellow]Non hai ancora giocato nessuna partita (o errore nel recupero).[/]")
    else:
        # Creiamo tabella storico
        table = Table(title=f"Storico di {state.username}")
        table.add_column("Data", style="dim")
        table.add_column("Avversario", style="bold white")
        table.add_column("Risultato", justify="center")
        table.add_column("Score", justify="right")

        for match in history:
            # Adatta le chiavi in base a come il tuo backend restituisce il JSON
            date = match.get('date', 'N/A')
            opponent = match.get('opponent', 'Unknown')
            result = match.get('result', '-') # WIN / LOSS
            score = match.get('score', '0-0')
            
            # Colora il risultato
            res_style = "[green]WIN[/]" if result == "WIN" else f"[red]{result}[/]"
            
            table.add_row(str(date), str(opponent), res_style, str(score))

        console.print(table)

    console.print("\n")
    questionary.text("Premi Invio per tornare indietro...").ask()