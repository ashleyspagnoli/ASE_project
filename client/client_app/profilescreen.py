import questionary
import asyncio
import time
from client_app.apicalls import api_change_password, api_change_email, api_change_username, api_view_data
from rich.console import Console

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
            if not risultato.success:
                console.print(f"[bold red]❌ Errore:[/bold red] {risultato.message}")
                time.sleep(2)
                continue
            # Supponiamo che risultato.data contenga le informazioni dell'utente
            email = risultato.data.get("email", "N/A")
            console.clear()
            console.print(f"[bold blue]--- USER PROFILE DETAILS ---[/]")
            console.print(f"[bold green]Username:[/] {username}")
            console.print(f"[bold green]Email:[/]{email}")
            console.print("\nPress Enter to go back.")
            input()
        elif scelta == "Go Back":
            break


def schermata_modifica_profilo(console:Console, CURRENT_USER_STATE: UserState): # Rimosso 'user'
    """Gestisce la modifica del profilo utente"""
    

    while True:

        console.clear()
        console.print(f"[bold magenta]--- Edit Profile ---[/]")
        scelta = questionary.select(
                "What do you want to change?",
                choices=["Password","Email","Username", "Go Back"]
            ).ask()
        



        if scelta == "Password":
            vecchia_password = questionary.password("Inserisci la vecchia password:").ask()
            nuova_password = questionary.password("Inserisci la nuova password:").ask()
            conferma_password = questionary.password("Conferma la nuova password:").ask()
            
            if nuova_password != conferma_password:
                console.print("[bold red]Errore: Le password non coincidono![/]")
                time.sleep(2)
                continue
            
            # Chiama API senza token
            risultato = asyncio.run(api_change_password(vecchia_password, nuova_password,CURRENT_USER_STATE ))

            if risultato.success:
                console.print(f"[bold green]✔️[/bold green] {risultato.message}")
                time.sleep(2)
                if risultato.message== "Password changed! Please login again.":
                    return # Forza il logout tornando alla schermata_profilo
            else:
                console.print(f"[bold red]❌ Errore:[/bold red] {risultato.message}")
                time.sleep(3)
        


        elif scelta == "Email":
            old_email = questionary.text("Inserisci la vecchia email:").ask()
            nuova_email = questionary.text("Inserisci la nuova email:").ask()

            risultato = asyncio.run(api_change_email(old_email, nuova_email,CURRENT_USER_STATE ))
            if risultato.success:
                console.print(f"[bold green]✔️[/bold green] {risultato.message}")
                time.sleep(2)
                return # Forza il logout tornando alla schermata_profilo
            else:
                console.print(f"[bold red]❌ Errore:[/bold red] {risultato.message}")
                time.sleep(2)
            

        

        elif scelta == "Username":
            nuovo_username = questionary.text("Inserisci il nuovo username:").ask()
            risultato = asyncio.run(api_change_username(nuovo_username,CURRENT_USER_STATE ))
            if risultato.success:
                console.print(f"[bold green]✔️[/bold green] {risultato.message}")
                time.sleep(2)
                return # Forza il logout tornando alla schermata_profilo
            else:
                console.print(f"[bold red]❌ Errore:[/bold red] {risultato.message}")
                time.sleep(2)
            

        elif scelta == "Go Back":
            return # Torna a schermata_profilo





