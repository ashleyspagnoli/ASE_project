import asyncio
import time
from rich.console import Console
import questionary
from client_app.apicalls import api_get_deck_collection

class UserState:
    """Contiene lo stato globale dell'utente loggato."""
    def __init__(self):
        self.token = None
        self.username = None


def schermata_partita(console: Console, CURRENT_USER_STATE: UserState):
    console.clear()
    console.print("[bold blue]--- LOBBY MATCHMAKING ---[/]")

    # --- FASE 1: Selezione del Deck ---
    console.print("Caricamento dei tuoi deck...")
    
    # Chiamata API per ottenere i deck
    result =  asyncio.run(api_get_deck_collection(CURRENT_USER_STATE))
    decks = result.get('data', []) if result and result.get('success') else []

    if not decks:
        console.print("[bold red]Non hai nessun deck! Crea un mazzo in Decks prima di giocare.[/]")
        questionary.text("Premi Invio per tornare indietro...").ask()
        return

    # Creazione menu di scelta (Slot: Nome)
    deck_choices = []
    deck_map = {} # Mappa label -> id_deck

    # Ordina per slot
    for deck in sorted(decks, key=lambda x: x.get('slot', 0)):
        slot = deck.get('slot')
        name = deck.get('name', 'Senza Nome')
        deck_id = deck.get('_id')
        
        label = f"Slot {slot}: {name}"
        deck_choices.append(label)
        deck_map[label] = deck_id

    deck_choices.append("Annulla")

    scelta = questionary.select(
        "Con quale deck vuoi scendere in campo?",
        choices=deck_choices
    ).ask()

    if scelta == "Annulla" or scelta is None:
        return
    selected_deck_id = deck_map[scelta]
    return 