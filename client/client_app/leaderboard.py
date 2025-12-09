import questionary
import asyncio
import time
from client_app.apicalls import api_get_leaderboard
from rich.console import Console

class UserState:
    """Contiene lo stato globale dell'utente loggato."""
    def __init__(self):
        self.token = None
        self.username = None

# Variabile Globale per la pagina selezionata


def schermata_leaderboard(console:Console,CURRENT_USER_STATE: UserState):
    """Mostra la classifica dei giocatori."""
    
    SELECTED_PAGE = 1
    while True:
        console.clear()
        console.print("[bold blue]--- LEADERBOARD ---[/]")
        result = asyncio.run(api_get_leaderboard(SELECTED_PAGE,CURRENT_USER_STATE=CURRENT_USER_STATE))
        print(result)

        if result!=[]:
            console.print(f"[bold yellow]--- Page {SELECTED_PAGE} ---[/]")
            for idx, entry in enumerate(result, start=1 + (SELECTED_PAGE - 1) * 10):
                console.print(f"{idx}. {entry['username']} - Wins: {entry['wins']}, Losses: {entry['losses']}")
        else:
            console.print("[bold red]No entries found for this page.[/]")
            
        scelta = questionary.select(
            message="Navigate Leaderboard:",
                choices=["<-","->","Write Page Number","Go Back"]

            ).ask()
        if scelta == "<-":
            if SELECTED_PAGE > 1:
                SELECTED_PAGE -= 1

        elif scelta == "->":
            SELECTED_PAGE += 1

        elif scelta == "Write Page Number":
            page_number = questionary.text("Enter page number:").ask()
            if page_number.isdigit() and int(page_number) >= 1:
                SELECTED_PAGE = int(page_number)
            else:
                console.print("[bold red]Invalid page number![/]")
                time.sleep(2)
        
        elif scelta == "Go Back":
            break
    