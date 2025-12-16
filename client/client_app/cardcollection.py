import questionary
import asyncio
import time
from client_app.apicalls import api_get_card_collection, api_get_deck_collection, api_create_deck, api_delete_deck
from client_app.utils import stampa_deck_visuale
from rich.console import Console
import json
from typing import Dict, Any, List

class UserState:
    """Contiene lo stato globale dell'utente loggato."""
    def __init__(self):
        self.token = None
        self.username = None

def fromid_to_card(card_id: int):
    """Converte id della carta in una visualizzazione della carta tramite numero e emoji."""
    #l'id è nella forma tipo: h2 dove h sta per hearts, d per diamons, c per club, s per spades
    if card_id is "JOKER":
        return "JOKER"
    
    tipo = card_id[0]
    numero = card_id[1:]
    if tipo == 'h':
        emoji = '❤️'
    elif tipo == 'd':
        emoji = '♦️'
    elif tipo == 'c':
        emoji = '♣️'
    elif tipo == 's':
        emoji = '♠️'
    else:
        emoji = ''
    return f"{numero} {emoji}"


def deck_creation_screen(console: Console, CURRENT_USER_STATE: UserState):
    """Schermata per la creazione di un nuovo deck con controllo slot occupati."""
    
    # --- 1. Recupero dei deck esistenti ---
    console.clear()
    console.print("[bold blue]--- DECK CREATION PAGE ---[/]")
    console.print("Loading existing decks...")
    
    # Recuperiamo la collezione per vedere gli slot occupati
    collection_result = asyncio.run(api_get_deck_collection(CURRENT_USER_STATE=CURRENT_USER_STATE))
    
    occupied_slots = {}
    if collection_result and collection_result.get('success'):
        for d in collection_result.get('data', []):
            s = d.get('slot')
            n = d.get('name', 'Unnamed')
            occupied_slots[str(s)] = n # Usiamo stringhe per le chiavi per coerenza

    # --- 2. Loop Selezione Slot ---
    selected_slot_clean = None
    
    while True:
        console.clear()
        console.print("[bold blue]--- DECK CREATION PAGE ---[/]")
        
        # Creiamo le scelte dinamiche
        slot_choices = []
        for i in range(1, 6): # Slot da 1 a 5
            slot_str = str(i)
            if slot_str in occupied_slots:
                # Slot Occupato
                deck_name = occupied_slots[slot_str]
                slot_choices.append(f"{i} (Occupato: {deck_name})")
            else:
                # Slot Libero
                slot_choices.append(f"{i} (Libero)")
        
        slot_choices.append("Cancel")

        scelta_raw = questionary.select(
            "Select the slot to save the new deck:",
            choices=slot_choices,
        ).ask()

        if scelta_raw == "Cancel" or scelta_raw is None:
            return

        # Estraiamo il numero puro dallo slot (es. "1 (Occupato...)" -> "1")
        selected_slot_clean = scelta_raw.split(" ")[0]

        # Se lo slot è occupato, chiediamo conferma
        if selected_slot_clean in occupied_slots:
            deck_to_overwrite = occupied_slots[selected_slot_clean]
            confirm = questionary.confirm(
                f"Lo slot {selected_slot_clean} è già occupato da '{deck_to_overwrite}'. Vuoi sovrascriverlo?",
                default=False
            ).ask()

            if not confirm:
                continue # Torna all'inizio del while (scelta slot)
            
            # Se conferma, usciamo dal loop e procediamo
            break
        else:
            # Se è libero, usciamo dal loop e procediamo
            break

    # --- 3. Inserimento Nome ---
    sceltanome = questionary.text(
        "Enter the name of the new deck (or type 'cancel' to go back):"
    ).ask()
    
    if sceltanome.lower() == 'cancel':
        return

    # --- 4. Selezione Carte (Logica Originale Mantenuta) ---
    suites = ['hearts ❤️', 'diamonds ♦️', 'clubs ♣️', 'spades ♠️', 'cancel']
    cards = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', 'cancel']
    deck = []
    
    # Copia delle suite disponibili per rimuoverle man mano
    available_suites = suites.copy() 

    for i in range(0, 4):
        console.print(f"\n[bold]Selection {i+1}/4[/]")
        
        sceltasuite = questionary.select(
            "Select the suit for the deck:",
            choices=available_suites, # Usiamo la lista che si accorcia
        ).ask()

        selected_suite = ''
        if sceltasuite == 'hearts ❤️':
            selected_suite = 'h'
        elif sceltasuite == 'diamonds ♦️':
            selected_suite = 'd'
        elif sceltasuite == 'clubs ♣️':
            selected_suite = 'c'
        elif sceltasuite == 'spades ♠️':
            selected_suite = 's'
        elif sceltasuite == 'cancel':
            return
        
        scelta = questionary.select(
            "Select the card for the deck:",
            choices=cards,
        ).ask()

        cardid1 = ""
        cardid2 = ""
        selected_card = ""

        # --- LOGICA ACCOPPIAMENTI ---
        if scelta == 'cancel':
            return

        elif scelta == cards[0]: # 2
            selected_card = '2'
            cardid1 = selected_suite + selected_card
            cardid2 = selected_suite + 'K' # K è cards[11]

        elif scelta == cards[1]: # 3
            selected_card = '3'
            cardid1 = selected_suite + selected_card
            cardid2 = selected_suite + 'Q' # Q è cards[10]

        elif scelta == cards[2]: # 4
            selected_card = '4'
            cardid1 = selected_suite + selected_card
            cardid2 = selected_suite + 'J' # J è cards[9]

        elif scelta == cards[3]: # 5
            selected_card = '5'
            cardid1 = selected_suite + selected_card
            cardid2 = selected_suite + '10' # 10 è cards[8]

        elif scelta == cards[4]: # 6
            selected_card = '6'
            cardid1 = selected_suite + selected_card
            cardid2 = selected_suite + '9' # 9 è cards[7]
            
        elif scelta == cards[5]: # 7
            selected_card = '7'
            cardid1 = selected_suite + selected_card
            cardid2 = selected_suite + '8' # 8 è cards[6]

        elif scelta == cards[6]: # 8
            selected_card = '8'
            cardid1 = selected_suite + selected_card
            # Caso speciale per l'8: chiede se accoppiare con A o 7? 
            # (Nel tuo codice originale c'era una logica specifica qui)
            scelta2 = questionary.select(
                f"Select the second card for the suite {selected_suite}:",
                choices=['A', '7'], 
            ).ask()
            cardid2 = selected_suite + scelta2

        elif scelta == cards[7]: # 9
            selected_card = '9'
            cardid1 = selected_suite + selected_card
            cardid2 = selected_suite + '6' 

        elif scelta == cards[8]: # 10
            selected_card = '10'
            cardid1 = selected_suite + selected_card
            cardid2 = selected_suite + '5' 

        elif scelta == cards[9]: # J
            selected_card = 'J'
            cardid1 = selected_suite + selected_card
            cardid2 = selected_suite + '4'

        elif scelta == cards[10]: # Q
            selected_card = 'Q'
            cardid1 = selected_suite + selected_card
            cardid2 = selected_suite + '3' 

        elif scelta == cards[11]: # K
            selected_card = 'K'
            cardid1 = selected_suite + selected_card
            cardid2 = selected_suite + '2' 

        elif scelta == cards[12]: # A
            selected_card = 'A'
            cardid1 = selected_suite + selected_card
            cardid2 = selected_suite + '8' 

        # Aggiunta al deck
        deck.append(cardid1)
        deck.append(cardid2)
        
        # Feedback visivo
        try:
            console.print(f"Added cards: {fromid_to_card(cardid1)} and {fromid_to_card(cardid2)}")
        except:
            console.print(f"Added cards: {cardid1} and {cardid2}")
            
        time.sleep(0.5)
        
        # Rimuovi la suite usata dalle scelte future
        if sceltasuite in available_suites:
            available_suites.remove(sceltasuite)

    # --- 5. Creazione Deck ---
    with console.status("[bold green]Saving deck...[/]", spinner="dots"):
        response = asyncio.run(api_create_deck(
            deck=deck,
            deck_name=sceltanome,
            deck_slot=int(selected_slot_clean),
            CURRENT_USER_STATE=CURRENT_USER_STATE
        ))
    
    # --- 6. Visualizzazione Risultato ---
    
    # Gestione generica della risposta (sia che arrivi come dict o oggetto)
    success = False
    msg = ""
    
    if isinstance(response, dict):
        success = response.get('success', True) # Assumiamo true se manca il campo ma non è esploso
        msg = response.get('message', 'Operazione completata')
    else:
        # Se è un oggetto Pydantic o Namespace
        success = getattr(response, 'success', True)
        msg = getattr(response, 'message', str(response))

    if success:
        console.clear()
        console.print(f"[bold green]✅ Deck Created Successfully![/]")
        console.print(f"Nome: [bold white]{sceltanome}[/]")
        console.print(f"Slot: [cyan]{selected_slot_clean}[/]")
        console.print("")
        
        # --- QUI RICHIAMIAMO LA VISUALIZZAZIONE GRAFICA ---
        stampa_deck_visuale(console, deck)
        # --------------------------------------------------

        console.print("\n")
        questionary.text("Premi Invio per tornare al menu...").ask()
    else:
        console.print(f"[bold red]❌ Errore durante la creazione: {msg}[/]")
        time.sleep(4)
    


def deck_view_screen(console:Console,CURRENT_USER_STATE: UserState):
    while True:
            console.clear()
            console.print("[bold blue]--- GESTIONE DECK ---[/]")

            # 1. Chiamata API per ottenere la lista aggiornata
            result = asyncio.run(api_get_deck_collection(CURRENT_USER_STATE=CURRENT_USER_STATE))
            
            if not result or not result.get('success'):
                console.print("[bold red]Errore nel recupero dei deck o nessun deck trovato.[/]")
                questionary.text("Premi Invio per tornare indietro...").ask()
                break

            decks = result.get('data', [])

            # 2. Creazione delle opzioni per il menu
            # Creiamo un dizionario per mappare "Label del menu" -> "Oggetto Deck"
            deck_map = {}
            menu_choices = []

            # Ordiniamo i deck per slot per una visualizzazione più pulita
            decks_sorted = sorted(decks, key=lambda x: x.get('slot', 0))

            for deck in decks_sorted:
                slot = deck.get('slot', '?')
                name = deck.get('name', 'Senza Nome')
                
                # Etichetta: "1: NomeDeck"
                label = f"{slot}: {name}"
                
                menu_choices.append(label)
                deck_map[label] = deck

            # Aggiungiamo l'opzione per tornare al menu principale
            menu_choices.append("Indietro")

            # 3. Mostra il menu di selezione Deck
            scelta_deck = questionary.select(
                "Seleziona un deck:",
                choices=menu_choices
            ).ask()

            # Se l'utente sceglie "Indietro", esce dal loop while e torna al menu principale
            if scelta_deck == "Indietro" or scelta_deck is None:
                return

            # 4. Recupero dell'oggetto deck selezionato
            selected_deck = deck_map[scelta_deck]
            deck_id = selected_deck.get('_id')
            deck_name = selected_deck.get('name')

            # 5. Sottomenu per il singolo Deck
            while True:
                console.clear()
                
                # Header del deck
                console.print(f"[bold yellow]--- DETTAGLI DECK ---[/]")
                console.print(f"Nome: [bold white]{deck_name}[/]")
                console.print(f"Slot: [cyan]{selected_deck.get('slot')}[/]")
                console.print("") # Spazio
                
                # --- VISUALIZZAZIONE CARTE ---
                cards_in_deck = selected_deck.get('cards', [])
                stampa_deck_visuale(console, cards_in_deck)
                # -----------------------------

                azione = questionary.select(
                    "Opzioni:",
                    choices=[
                        "Elimina Deck", 
                        "Indietro"
                    ]
                ).ask()

                if azione == "Elimina Deck":
                    confirm = questionary.confirm(
                        f"Sei sicuro di voler eliminare '{deck_name}'?",
                        default=False
                    ).ask()
                    
                    if confirm:
                        # Chiamata API Delete
                        delete_result = asyncio.run(api_delete_deck(deck_id, CURRENT_USER_STATE))
                        
                        if delete_result and delete_result.get('success', False):
                             console.print(f"[green]Deck '{deck_name}' eliminato con successo![/]")
                             time.sleep(1.5)
                             break # Esce dal sottomenu e ricarica la lista principale
                        else:
                             err_msg = delete_result.get('detail', 'Errore sconosciuto')
                             console.print(f"[red]Errore: {err_msg}[/]")
                             time.sleep(2)
                
                
                elif azione == "Indietro":
                    break # Torna alla lista dei deck
        


def deck_screen(console:Console,CURRENT_USER_STATE: UserState):
    """Mostra la schermata del deck."""
    
    while True:
        console.clear()
        console.print("[bold blue]--- DECK PAGE ---[/]")
        scelta=questionary.select(
            "What do you want to do?",
            choices=["View Decks", "Create Deck", "Go Back"],
        ).ask()
        if scelta == "Go Back":
            return
        elif scelta == "View Decks":
            deck_view_screen(console,CURRENT_USER_STATE)
            
        elif scelta == "Create Deck":
            deck_creation_screen(console,CURRENT_USER_STATE)


def schermata_cardcollection(console:Console,CURRENT_USER_STATE: UserState):
    """Mostra la collezione di carte dell'utente."""
    while True:
        console.clear()
        console.print("[bold blue]--- CARDS ---[/]")
        scelta=questionary.select(
            "What do you want to do?",
            choices=["View Card Collection", "Deck Page" , "Go Back"],
        ).ask()

        if scelta == "Go Back":
            break

        elif scelta == "View Card Collection":
            console.clear()
            
            # --- 1. Recupero Dati ---
            result = asyncio.run(api_get_card_collection(CURRENT_USER_STATE=CURRENT_USER_STATE))
            cards_list: List[Dict[str, str]] = result.get('data', [])
            
            console.print("[bold yellow]--- Card Collection ---[/]\n")

            if not cards_list:
                console.print("[italic red]Nessuna carta nella collezione.[/]")
            else:
                # --- 2. Preparazione dei Contenitori ---
                # Creiamo liste separate per ogni categoria
                suits_data = {
                    'h': [], # h = Hearts (Cuori)
                    'd': [], # d = Diamonds (Quadri)
                    'c': [], # c = Clubs (Fiori)
                    's': [], # s = Spades (Picche)
                    'JOKER': []
                }

                # --- 3. Distribuzione delle carte nei contenitori ---
                for item in cards_list:
                    card_id = item.get("id")
                    
                    if card_id == "JOKER":
                        suits_data['JOKER'].append(card_id)
                    else:
                        # Il primo carattere è il seme (h, d, c, s)
                        suit_char = card_id[0]
                        if suit_char in suits_data:
                            suits_data[suit_char].append(card_id)

                # --- 4. Logica di Ordinamento (Opzionale ma consigliata) ---
                # Mappa per ordinare correttamente (altrimenti 10 verrebbe prima di 2)
                rank_order = {
                    'A': 1, '2': 2, '3': 3, '4': 4, '5': 5, 
                    '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 
                    'J': 11, 'Q': 12, 'K': 13
                }
                
                def get_sort_key(cid):
                    # Rimuove il seme (es. "h10" -> "10") e converte in numero
                    rank = cid[1:] 
                    return rank_order.get(rank, 0)

                # --- 5. Stampa a schermo ---
                
                # Ordine di visualizzazione dei semi
                display_order = [('h', 'Hearts'), ('d', 'Diamonds'), ('c', 'Clubs'), ('s', 'Spades')]

                for suit_char, suit_name in display_order:
                    # Ordina le carte di questo seme
                    cards_in_suit = sorted(suits_data[suit_char], key=get_sort_key)
                    
                    if cards_in_suit:
                        # Converte gli ID in emoji/testo usando la tua funzione fromid_to_card
                        # E li unisce con uno spazio " "
                        row_string = "  ".join([fromid_to_card(cid) for cid in cards_in_suit])
                        console.print(f"{row_string}")
                    else:
                        # Opzionale: se non hai carte di quel seme puoi non stampare nulla o stampare vuoto
                        pass 

                # Stampa dei Joker alla fine
                if suits_data['JOKER']:
                    console.print("\n[bold purple]Jokers:[/]")
                    joker_row = "  ".join([fromid_to_card(cid) for cid in suits_data['JOKER']])
                    console.print(f"{joker_row}")

            console.print("\n") # Spazio finale
            questionary.text("Press Enter to continue...").ask()
        
        elif scelta is "Deck Page":
            deck_screen(console,CURRENT_USER_STATE)
        


