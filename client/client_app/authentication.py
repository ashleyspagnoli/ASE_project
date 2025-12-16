import questionary
import asyncio
import time
from client_app.apicalls import api_login, api_register
from rich.console import Console
import sys
import re  # <--- Necessario per validare la mail


class UserState:
    """Contiene lo stato globale dell'utente loggato."""
    def __init__(self):
        self.token = None
        self.username = None

def flusso_autenticazione(console:Console, CURRENT_USER_STATE: UserState):
    """Questa funzione NON esce finché l'utente non è loggato."""
    while True:
        console.clear()
        scelta = questionary.select(
            "Welcome to Guerra! What do you want to do?",
            choices=["Login", "Register", "Quit"]
        ).ask()

        if scelta == "Login":
            success = schermata_login(console, CURRENT_USER_STATE)
            if success:
                return True # Successo nel login, esce dal loop
            
        elif scelta == "Register":
            schermata_register(console, CURRENT_USER_STATE)
            
        elif scelta == "Quit":
            console.print("Arrivederci!")
            sys.exit()




def schermata_login(console:Console, CURRENT_USER_STATE: UserState):
    """Gestisce l'input di login"""
    console.print("[bold cyan]--- LOGIN ---[/]")
    username = questionary.text("Inserisci Username:").ask()
    password = questionary.password("Inserisci Password:").ask()
    
    with console.status("[bold green]Verifica credenziali in corso..."):
        # api_login ora imposta direttamente CURRENT_USER_STATE.token/.username
        result = asyncio.run(api_login(username, password, CURRENT_USER_STATE ))
        
    if result.success:
        # Qui leggiamo CURRENT_USER_STATE per l'username
        console.print(f"[bold green]Successo! Benvenuto {CURRENT_USER_STATE.username}![/]")
        time.sleep(2)
        return True # Successo nel login
    else:
        # Stampiamo l'errore che l'API ci ha restituito
        console.print(f"[bold red]Errore:[/bold red] {result.message}")
        time.sleep(2)
        return False # Fallimento



def schermata_register(console: Console, CURRENT_USER_STATE: UserState):
    # Logica di registrazione
    console.print("[bold orange3]--- REGISTRAZIONE NUOVO UTENTE ---[/]")
    
    while True:
        # 1. Username (Opzionale: puoi mettere un controllo lunghezza anche qui se vuoi)
        username = questionary.text("Choose a username:").ask()
        if username is None: return False # Gestione uscita (Ctrl+C)

        # 2. Email con Validazione Regex (qualcosa@altro.altro)
        # La regex r"[^@]+@[^@]+\.[^@]+" controlla che ci sia testo, poi @, poi testo, poi un punto.
        email = questionary.text(
            "Insert your Email:",
            validate=lambda text: True if re.match(r"[^@]+@[^@]+\.[^@]+", text) else "Invalid email format! (must be x@y.z)"
        ).ask()
        if email is None: return False

        # 3. Password con controllo lunghezza > 3
        password = questionary.password(
            "Choose a password:",
            validate=lambda text: True if len(text) > 3 else "Password too short! Must be > 3 chars."
        ).ask()
        if password is None: return False

        # 4. Conferma Password
        confirm = questionary.password("Confirm Password:").ask()
        if confirm is None: return False
        
        # Controllo corrispondenza (questo si fa dopo perché servono due campi)
        if password != confirm:
            console.print("[bold red]Error: Passwords don't match![/]")
            time.sleep(2)
            continue # Ricomincia il ciclo while chiedendo di nuovo i dati

        # Chiamata API
        with console.status("[bold green]User Creation..."):
            result = asyncio.run(api_register(username, password, email, CURRENT_USER_STATE))
        
        if result.success:
            console.print("[bold green]Registration successful! Please log in.[/]")
            time.sleep(2)
            return True
        else:
            # Se la registrazione fallisce (es. utente già esistente), stampiamo l'errore
            console.print(f"[bold red]Error: [/bold red]{result.message}")
            
            # Chiediamo se vuole riprovare o uscire
            retry = questionary.confirm("Do you want to try again?").ask()
            if not retry:
                return False
            # Se retry è True, il while True ricomincia
    

