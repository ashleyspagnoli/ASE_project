import questionary
import asyncio
import time
from client_app.apicalls import api_change_password, api_change_email, api_change_username, api_view_data
from rich.console import Console
import re  # Assicurati di avere questo import in cima al file


class UserState:
    """Contiene lo stato globale dell'utente loggato."""
    def __init__(self):
        self.token = None
        self.username = None



def schermata_profilo(console:Console, CURRENT_USER_STATE: UserState): # Rimosso 'user'
    """Mostra le informazioni del profilo utente"""
    if not CURRENT_USER_STATE.username or not CURRENT_USER_STATE.token:
        return
    
    username = CURRENT_USER_STATE.username
    
    while True:
        console.clear()
        console.print(f"[bold blue]--- PROFILO UTENTE: {username} ---[/]")
        console.print(f"Username: [bold]{username}[/]")
        scelta = questionary.select(
                "You are in your profile. What do you want to do?",
                choices=["Edit profile", "View Profile" , "Go Back"]
            ).ask()
        if scelta == "Edit profile":
            # Se la modifica ha successo e forza il logout, usciamo da qui.
            schermata_modifica_profilo(console, CURRENT_USER_STATE) 
            if not CURRENT_USER_STATE.token:
                return # Torna al main menu per il logout forzato
        elif scelta == "View Profile":
            risultato = asyncio.run(api_view_data(CURRENT_USER_STATE))
            # Supponiamo che risultato.data contenga le informazioni dell'utente
            email = risultato["email"]
            console.clear()
            console.print(f"[bold blue]--- USER PROFILE DETAILS ---[/]")
            console.print(f"[bold green]Username:[/] {username}")
            console.print(f"[bold green]Email:[/]{email}")
            console.print("\nPress Enter to go back.")
            input()
        elif scelta == "Go Back":
            break




def schermata_modifica_profilo(console: Console, CURRENT_USER_STATE: UserState):
    """Gestisce la modifica del profilo utente con validazione"""

    # Regex semplice per validare email
    EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"

    while True:
        console.clear()
        console.print(f"[bold magenta]--- Edit Profile ---[/]")
        scelta = questionary.select(
                "What do you want to change?",
                choices=["Password", "Email", "Username", "Go Back"]
            ).ask()

        # --- CAMBIO PASSWORD ---
        if scelta == "Password":
            vecchia_password = questionary.password("Inserisci la vecchia password:").ask()
            if not vecchia_password: continue # Se annulla/vuoto torna al menu
            
            nuova_password = questionary.password("Inserisci la nuova password (min 8 car.):").ask()
            if not nuova_password: continue

            # 1. CONTROLLO REQUISITI PASSWORD
            if len(nuova_password) < 8:
                console.print("[bold red]❌ Errore: La password deve essere di almeno 8 caratteri![/]")
                time.sleep(2)
                continue
            
            conferma_password = questionary.password("Conferma la nuova password:").ask()
            
            # 2. CONTROLLO CORRISPONDENZA
            if nuova_password != conferma_password:
                console.print("[bold red]❌ Errore: Le password non coincidono![/]")
                time.sleep(2)
                continue
            
            # Chiama API
            risultato = asyncio.run(api_change_password(vecchia_password, nuova_password, CURRENT_USER_STATE))

            if risultato.success:
                console.print(f"[bold green]✔️[/bold green] {risultato.message}")
                time.sleep(2)
                if risultato.message == "Password changed! Please login again.":
                    return 
            else:
                console.print(f"[bold red]❌ Errore:[/bold red] {risultato.message}")
                time.sleep(3)

        # --- CAMBIO EMAIL ---
        elif scelta == "Email":
            old_email = questionary.text("Inserisci la vecchia email:").ask()
            if not old_email: continue

            nuova_email = questionary.text("Inserisci la nuova email:").ask()
            if not nuova_email: continue

            # 1. CONTROLLO FORMATO EMAIL
            if not re.match(EMAIL_REGEX, nuova_email):
                console.print("[bold red]❌ Errore: Formato email non valido! (es. nome@dominio.com)[/]")
                time.sleep(2)
                continue

            risultato = asyncio.run(api_change_email(old_email, nuova_email, CURRENT_USER_STATE))
            
            if risultato.success:
                console.print(f"[bold green]✔️[/bold green] {risultato.message}")
                time.sleep(2)
                return 
            else:
                console.print(f"[bold red]❌ Errore:[/bold red] {risultato.message}")
                time.sleep(2)

        # --- CAMBIO USERNAME ---
        elif scelta == "Username":
            nuovo_username = questionary.text("Inserisci il nuovo username:").ask()
            
            # Opzionale: Controllo username vuoto o troppo corto
            if not nuovo_username or len(nuovo_username) < 3:
                console.print("[bold red]❌ Errore: L'username deve avere almeno 3 caratteri![/]")
                time.sleep(2)
                continue

            risultato = asyncio.run(api_change_username(nuovo_username, CURRENT_USER_STATE))
            
            if risultato.success:
                console.print(f"[bold green]✔️[/bold green] {risultato.message}")
                time.sleep(2)
                return 
            else:
                console.print(f"[bold red]❌ Errore:[/bold red] {risultato.message}")
                time.sleep(2)

        elif scelta == "Go Back" or scelta is None:
            return




