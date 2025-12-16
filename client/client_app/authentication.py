import questionary
import asyncio
import time
from client_app.apicalls import api_login, api_register
from rich.console import Console
import sys

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



def schermata_register(console:Console, CURRENT_USER_STATE: UserState):
    # Logica di registrazione
    console.print("[bold orange3]--- REGISTRAZIONE NUOVO UTENTE ---[/]")
    while True:
        username = questionary.text("Chose a username:").ask()
        email = questionary.text("Insert your Email:").ask()
        password = questionary.password("Chose a password:").ask()
        confirm = questionary.password("Confirm Password:").ask()
        
        if password != confirm:
            console.print("[bold red]Error: Password don't match![/]")
            time.sleep(2)
            continue

        with console.status("[bold green]User Creation..."):
            result = asyncio.run(api_register(username, password, email,CURRENT_USER_STATE ))

        
        if result.success:
            console.print("[bold green]Registration succesful! Please log in.[/]")
            time.sleep(2)
            return True
        else:
            console.print(f"[bold red]Error: [/bold red]{result.message}")
            time.sleep(2)
            return False
    

