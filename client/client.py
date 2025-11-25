import questionary
import time
import sys
import asyncio
import httpx
from rich.console import Console
from fastapi import HTTPException, status # Manteniamo HTTPException per coerenza con l'output d'errore



console = Console()


class UserState:
    """Contiene lo stato globale dell'utente loggato."""
    def __init__(self):
        self.token = None
        self.username = None

# ⚠️ Variabile Globale: Istanzia questa classe una sola volta
CURRENT_USER_STATE = UserState()



AUTH_SERVICE_URL = "https://localhost:5004"

class ApiResult:
    def __init__(self, success: bool, message: str):
        self.success = success
        self.message = message


# --- FUNZIONI DI SERVIZIO ---

async def api_validate_token_internal():
    """Versione interna per validare il token dopo il login e recuperare l'username."""
    token = CURRENT_USER_STATE.token
    if not token:
        return None
        
    async with httpx.AsyncClient(verify=False) as client:
        try:
            validate_url = f"{AUTH_SERVICE_URL}/users/validate-token"
            response = await client.get(
                validate_url,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status() 
            
            data = response.json()
            # AGGIORNAMENTO DELLO STATO GLOBALE con i dati validati
            return data

        except (httpx.HTTPStatusError, httpx.RequestError):
            return None # Token non valido o servizio non raggiungibile


async def api_login(username, password):
    async with httpx.AsyncClient(verify=False) as client:
        try:
            login_url = f"{AUTH_SERVICE_URL}/users/login"
            body = {"username": username, "password": password}
            
            response = await client.post(
                login_url,
                json=body,
            )
            
            response.raise_for_status() 
            data = response.json()
            CURRENT_USER_STATE.token = data.get("token")
            CURRENT_USER_STATE.username = username
            return ApiResult(success=True, message="Login successful")
    
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return ApiResult(success=False, message="Username o password errati.") 
            # Qui rilanciamo gli errori generici del servizio

        except httpx.RequestError:
            return ApiResult(success=False, message="Servizio di autenticazione non raggiungibile.")
    

async def api_register(username, password, email):
    # Logica di registrazione: OK
    async with httpx.AsyncClient(verify=False) as client:
        try:
            register_url = f"{AUTH_SERVICE_URL}/users/register"
            body = {"username": username, "password": password, "email": email}
            
            response = await client.post(register_url, json=body)
            response.raise_for_status() 
            
            return ApiResult(success=True, message="Registration successful. Please login to continue.")

        except httpx.HTTPStatusError as e:
            # Cattura errori 400 (utente/email già registrato)
            if e.response.status_code == 400:
                detail = e.response.json().get('detail', "Errore di registrazione sconosciuto.")
                return ApiResult(success=False, message=detail)
            
        except httpx.RequestError:
            return ApiResult(success=False, message="Servizio di autenticazione non raggiungibile.")

# api_validate_token è ora api_validate_token_internal


async def api_change_password(old_password, new_password): #ENDPOINT IMPLEMENTATO FUNZIONANTE
    token = CURRENT_USER_STATE.token # Lettura dal globale
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            change_url = f"{AUTH_SERVICE_URL}/users/modify/change-password"
            headers = {"Authorization": f"Bearer {token}"}
            body = {"old_password": old_password, "new_password": new_password}
            
            response = await client.patch(
                change_url,
                headers=headers,
                json=body,
            )
            
            response.raise_for_status() 
            
            # Se la password cambia, il token vecchio è INVALIDO.
            # Rimuoviamo il token per forzare il re-login.

            loginresult = await (api_login(CURRENT_USER_STATE.username, new_password))
            if loginresult.success:
                console.print("[bold green]Re-login automatico riuscito dopo il cambio password.[/]")
                time.sleep(2)
                return ApiResult(success=True, message="Password changed! Re-login is automatic.")
            else: 
                CURRENT_USER_STATE.token = None
                CURRENT_USER_STATE.username = None
                return ApiResult(success=True, message="Password changed! Please login again.") # Forza re-login manuale dal main loop

            
        except httpx.HTTPStatusError as e:
            # Gestione errore 401 (vecchia password sbagliata) o 422 (validazione)
            detail = e.response.json().get('detail', "Errore sconosciuto.")
            if e.response.status_code == 401:
                return ApiResult(success=False, message="Vecchia password non valida.")
            elif e.response.status_code == 422:
                return ApiResult(success=False, message="La nuova password non soddisfa i requisiti di sicurezza.")
            else:
                return ApiResult(success=False, message=f"Errore {e.response.status_code}: {detail}")
            
        except httpx.RequestError:
            return ApiResult(success=False, message="Servizio di autenticazione non raggiungibile.")

async def api_change_email(old_email,new_email):
    # ORA C'È DA IMPLEMENTARE BENE LE API PER CAMBIO EMAIL E USERNAME
    token = CURRENT_USER_STATE.token # Lettura dal globale
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            change_url = f"{AUTH_SERVICE_URL}/users/modify/change-email"
            headers = {"Authorization": f"Bearer {token}"}
            body = {"old_password": old_email, "new_password": new_email}
            
            response = await client.patch(
                change_url,
                headers=headers,
                json=body,
            )
            
            response.raise_for_status() 
            
            # Se la password cambia, il token vecchio è INVALIDO.
            # Rimuoviamo il token per forzare il re-login.

            loginresult = await (api_login(CURRENT_USER_STATE.username, new_password))
            if loginresult.success:
                console.print("[bold green]Re-login automatico riuscito dopo il cambio password.[/]")
                time.sleep(2)
                return ApiResult(success=True, message="Email Changed succesfully!")
            else: 
                CURRENT_USER_STATE.token = None
                CURRENT_USER_STATE.username = None
                return ApiResult(success=True, message="Password changed! Please login again.") # Forza re-login manuale dal main loop

            
        except httpx.HTTPStatusError as e:
            # Gestione errore 401 (vecchia password sbagliata) o 422 (validazione)
            detail = e.response.json().get('detail', "Errore sconosciuto.")
            if e.response.status_code == 401:
                return ApiResult(success=False, message="Vecchia password non valida.")
            elif e.response.status_code == 422:
                return ApiResult(success=False, message="La nuova password non soddisfa i requisiti di sicurezza.")
            else:
                return ApiResult(success=False, message=f"Errore {e.response.status_code}: {detail}")
            
        except httpx.RequestError:
            return ApiResult(success=False, message="Servizio di autenticazione non raggiungibile.")


# ORA C'È DA IMPLEMENTARE BENE LE API PER CAMBIO EMAIL E USERNAME

# ----------------------------------------------------------------------- login e registrazione

def schermata_login():
    """Gestisce l'input di login"""
    console.print("[bold cyan]--- LOGIN ---[/]")
    username = questionary.text("Inserisci Username:").ask()
    password = questionary.password("Inserisci Password:").ask()
    
    with console.status("[bold green]Verifica credenziali in corso..."):
        # api_login ora imposta direttamente CURRENT_USER_STATE.token/.username
        result = asyncio.run(api_login(username, password))
        
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



def schermata_register():
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
            result = asyncio.run(api_register(username, password, email))
        
        if result.success:
            console.print("[bold green]Registration succesful! Please log in.[/]")
            time.sleep(2)
            return True
        else:
            console.print(f"[bold red]Error: [/bold red]{result.message}")
            time.sleep(2)
            return False
    

def flusso_autenticazione():
    """Questa funzione NON esce finché l'utente non è loggato."""
    while True:
        console.clear()
        scelta = questionary.select(
            "Welcome to Guerra! What do you want to do?",
            choices=["Login", "Register", "Quit"]
        ).ask()

        if scelta == "Login":
            success = schermata_login()
            if success:
                return True # Successo nel login, esce dal loop
            
        elif scelta == "Register":
            schermata_register()
            
        elif scelta == "Quit":
            console.print("Arrivederci!")
            sys.exit()

# ----------------------------------------------------------------------- menu principale gioco
def menu_principale_gioco(): # Rimosso 'user'
    console.clear()

    if not CURRENT_USER_STATE.username or not CURRENT_USER_STATE.token:
        return True
    
    console.print("[bold green]--- MAIN MENU ---[/]")
    # 2. UI usa i dati dallo stato globale
    username = CURRENT_USER_STATE.username

    console.print(f"[bold purple]You are logged as : {username}[/]")
    
    while True:
        azione = questionary.select(
            "What do you want to do?",
            choices=["Explore", "Profile", "Logout", "Quit"]
        ).ask()
        
        if azione == "Logout":
            console.print("[yellow]Disconnection...[/]")
            CURRENT_USER_STATE.token = None # Rimuove lo stato
            CURRENT_USER_STATE.username = None
            return True # True = Logout, riavvia il ciclo di autenticazione

        elif azione == "Profile":
            schermata_profilo() # Rimosso 'user'
        
        elif azione == "Quit":
            console.print("Arrivederci!")
            return False # False = Chiudi il programma


        console.print(f"Hai scelto: {azione}")
    
# ----------------------------------------------------------------------- profilo utente


def schermata_modifica_profilo(): # Rimosso 'user'
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
            risultato = asyncio.run(api_change_password(vecchia_password, nuova_password))

            if risultato.success:
                console.print(f"[bold green]✔️[/bold green] {risultato.message}")
                time.sleep(2)
                if risultato.message== "Password changed! Please login again.":
                    return # Forza il logout tornando alla schermata_profilo
            else:
                console.print(f"[bold red]❌ Errore:[/bold red] {risultato.message}")
                time.sleep(3)
        
        elif scelta == "Email":
            nuova_email = questionary.text("Inserisci la nuova email:").ask()
            # AGGIUNGERE LOGICA API
            console.print("[bold green]Email cambiata con successo![/]")
            time.sleep(2)
        
        elif scelta == "Username":
            nuovo_username = questionary.text("Inserisci il nuovo username:").ask()
            # AGGIUNGERE LOGICA API
            console.print("[bold green]Username cambiato con successo![/]")
            time.sleep(2)

        elif scelta == "Go Back":
            return # Torna a schermata_profilo



def schermata_profilo(): # Rimosso 'user'
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
                choices=["Edit profile", "Quit"]
            ).ask()
        if scelta == "Edit profile":
            # Se la modifica ha successo e forza il logout, usciamo da qui.
            schermata_modifica_profilo()
            if not CURRENT_USER_STATE.token:
                return # Torna al main menu per il logout forzato
        elif scelta == "Quit":
            break



# --- MAIN ---
if __name__ == "__main__":
    while True:
        # 1. Blocca l'utente qui finché non si autentica
        flusso_autenticazione()
        
        # 2. Una volta autenticato (token in stato globale), avvia il gioco
        # Se CURRENT_USER_STATE.token è None, menu_principale_gioco non viene chiamato
        if CURRENT_USER_STATE.token:
            # Il gioco ritorna True (logout) o False (quit game)
            continue_game = menu_principale_gioco()
        
            if continue_game is False:
                break  # Chiude il programma
        
        # 3. Se CURRENT_USER_STATE.token è None (Logout o Password cambiata), il loop ricomincia per la riautenticazione