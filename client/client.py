import questionary
from rich.console import Console
import time
from client_app.profilescreen import schermata_profilo
from client_app.authentication import flusso_autenticazione
from client_app.leaderboard import schermata_leaderboard
from client_app.cardcollection import schermata_cardcollection
#from client_app.matchscreen import schermata_partita

console = Console()


class UserState:
    """Contiene lo stato globale dell'utente loggato."""
    def __init__(self):
        self.token = None
        self.username = None

# ⚠️ Variabile Globale: Istanzia questa classe una sola volta
CURRENT_USER_STATE = UserState()



# ----------------------------------------------------------------------- menu principale gioco
def menu_principale_gioco(): # Rimosso 'user'

    if not CURRENT_USER_STATE.username or not CURRENT_USER_STATE.token:
        return True
    
    
    
    while True:
        console.clear()

        console.print("[bold green]--- MAIN MENU ---[/]")
        username = CURRENT_USER_STATE.username

        console.print(f"[bold purple]You are logged as : {username}[/]")
        azione = questionary.select(
            "What do you want to do?",
            choices=["Play a Match", "Decks", "Profile", "Leaderboard" , "Logout", "Quit"]
        ).ask()
        
        if azione == "Logout":
            console.print("[yellow]Disconnection...[/]")
            CURRENT_USER_STATE.token = None # Rimuove lo stato
            CURRENT_USER_STATE.username = None
            return True # True = Logout, riavvia il ciclo di autenticazione

        elif azione == "Profile":
            schermata_profilo(console,CURRENT_USER_STATE) # Rimosso 'user'
            if not CURRENT_USER_STATE.token:
                return True # Forza il logout se il token è stato rimosso durante la modifica del profilo
            
        elif azione == "Leaderboard":
            schermata_leaderboard(console,CURRENT_USER_STATE)

        elif azione == "Decks":
            schermata_cardcollection(console,CURRENT_USER_STATE)

        elif azione == "Play a Match":
            #schermata_partita(console,CURRENT_USER_STATE)
            time.sleep(2)

        elif azione == "Quit":
            console.print("Arrivederci!")
            return False # False = Chiudi il programma


        console.print(f"Hai scelto: {azione}")
    
# ----------------------------------------------------------------------- profilo utente





# --- MAIN ---
if __name__ == "__main__":
    while True:
        # 1. Blocca l'utente qui finché non si autentica
        flusso_autenticazione(console, CURRENT_USER_STATE)
        
        # 2. Una volta autenticato (token in stato globale), avvia il gioco
        # Se CURRENT_USER_STATE.token è None, menu_principale_gioco non viene chiamato
        if CURRENT_USER_STATE.token:
            # Il gioco ritorna True (logout) o False (quit game)
            continue_game = menu_principale_gioco()
        
            if continue_game is False:
                break  # Chiude il programma
        
        # 3. Se CURRENT_USER_STATE.token è None (Logout o Password cambiata), il loop ricomincia per la riautenticazione