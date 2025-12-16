import asyncio
import time
from rich.console import Console
import questionary
from client_app.apicalls import api_get_deck_collection, api_join_matchmaking, api_get_match_status, api_get_hand, api_play_card, api_get_game_state
from rich.panel import Panel
from rich.align import Align
from rich.columns import Columns

class UserState:
    """Contiene lo stato globale dell'utente loggato."""
    def __init__(self):
        self.token = None
        self.username = None

SUIT_FULL_NAMES = {
    'h': 'hearts',
    'd': 'diamonds',
    'c': 'clubs',
    's': 'spades'
}
def convert_id_to_payload(card_id):
    if card_id == "JOKER":
        return {"value": "JOKER", "suit": "none"} # O gestiscilo come preferisci
    
    suit_char = card_id[0] # es. 'c'
    value = card_id[1:]    # es. '3' o '10'
    
    full_suit = SUIT_FULL_NAMES.get(suit_char, suit_char)
    return {"value": value, "suit": full_suit}

def fromid_to_card(card_id: str) -> str:
    """
    Converte un ID carta (es. 'h10', 'sK', 'JOKER') 
    in una stringa visiva (es. '10 ❤️', 'K ♠️', '🃏 Joker').
    """
    if not card_id:
        return "??"

    # 1. Gestione caso speciale JOKER
    if card_id == "JOKER":
        return "🃏 Joker"

    # 2. Mappa dei semi
    suit_map = {
        'h': '❤️',  # Hearts (Cuori)
        'd': '♦️',  # Diamonds (Quadri)
        'c': '♣️',  # Clubs (Fiori)
        's': '♠️'   # Spades (Picche)
    }

    # 3. Parsing della stringa
    # card_id[0] è il primo carattere (il seme)
    # card_id[1:] prende tutto dal secondo carattere in poi (il valore)
    try:
        suit_char = card_id[0]
        rank = card_id[1:]
        
        # Recupera l'emoji, se non trova il seme mette '?'
        suit_emoji = suit_map.get(suit_char, '?')
        
        # 4. Ritorna il formato "Valore Emoji"
        return f"{rank} {suit_emoji}"
        
    except IndexError:
        return card_id # Ritorna l'ID originale se la stringa è malformata

# Funzione helper per convertire 'c3' in {'value': '3', 'suit': 'clubs'}
def gamescreen(console: Console, game_id: str, CURRENT_USER_STATE: UserState):
    """
    Gestisce il flusso della partita:
    1. Scarica stato iniziale
    2. Loop Turni
    3. Gestione Waiting/Resolved/Finished
    """
    
    my_username = CURRENT_USER_STATE.username
    
    # Variabili locali per tenere traccia dello stato senza chiamare l'API inutilmente
    current_turn = 0
    opponent_name = "Avversario"
    
    # Loop Principale del Gioco
    while True:
        console.clear()
        
        # --- 1. RECUPERO DATI INIZIO TURNO ---
        # Scarichiamo lo stato per avere punteggi aggiornati e turno corrente
        game_state = asyncio.run(api_get_game_state(game_id, CURRENT_USER_STATE))
        
        if not game_state:
            console.print("[bold red]Errore critico: Impossibile recuperare lo stato della partita.[/]")
            break
            
        # Controllo se la partita è già finita (caso raro, ma possibile)
        winner = game_state.get("winner")
        if winner:
            console.clear()
            scores = game_state.get("scores", {})
            console.print(Panel(f"[bold gold1]WINNER IS: {winner}[/]", title="GAME OVER"))
            console.print(f"Punteggio Finale: {scores}")
            questionary.text("Premi Invio per tornare alla lobby...").ask()
            break

        # Aggiornamento variabili locali
        current_turn = game_state.get("turn_number", 0)
        scores = game_state.get("scores", {})
        
        # Identificazione Avversario (Logica per trovarlo nella lista players)
        players = game_state.get("players", [])
        for p in players:
            if p['name'] != my_username:
                opponent_name = p['name']
                break
        
        # --- 2. HEADER VISIVO (Top Left / Top Right) ---
        # Creiamo due pannelli o stringhe formattate
        my_score = scores.get(my_username, 0)
        opp_score = scores.get(opponent_name, 0)
        
        left_text = f"[bold cyan]Turno: {current_turn}[/]\n[bold green]{my_username}: {my_score}[/]"
        right_text = f"[bold red]VS[/]\n[bold yellow]{opponent_name}: {opp_score}[/]"
        
        # Usa Columns per distanziare sx e dx
        console.print(Columns([Align.left(left_text), Align.right(right_text)], expand=True))
        console.print("-" * console.width) # Linea divisoria

        # --- 3. RECUPERO MANO ---
        console.print("Tua mano:")
        hand_cards = asyncio.run( api_get_hand(game_id, CURRENT_USER_STATE))
        if not hand_cards:
            console.print("[italic]Mano vuota... partita in chiusura?[/]")
        
        # --- 4. SELEZIONE CARTA ---
        choices = []
        for item in hand_cards:
            cid = None
            
            # Caso 1: È un dizionario (come nel tuo caso)
            if isinstance(item, dict):
                val = item.get('value')
                suit = item.get('suit', '').lower() # es. 'hearts'
                
                if val == 'JOKER':
                    cid = "JOKER"
                elif suit and val:
                    # Prende la prima lettera del seme (hearts -> h, diamonds -> d)
                    # e ci attacca il valore. Es: 'h' + 'K' = 'hK'
                    cid = f"{suit[0]}{val}"
            
            # Caso 2: È già una stringa (es. 'hK') - Fallback per sicurezza
            elif isinstance(item, str):
                cid = item

            # Aggiungiamo alla lista se abbiamo trovato un ID valido
            if cid:
                visual_label = fromid_to_card(cid) 
                choices.append(questionary.Choice(title=visual_label, value=cid))
        
        # Aggiungi uscita di emergenza
        choices.append(questionary.Choice(title="🔙 Abbandona Partita", value="EXIT"))
        card_selected = questionary.select(
            "Scegli la carta da giocare:",
            choices=choices
        ).ask()

        # Gestione caso "Abbandona" o selezione annullata (CTRL+C)
        if card_selected == "EXIT" or card_selected is None:
            console.print("[yellow]Hai abbandonato la vista della partita.[/]")
            break

        # --- 5. GIOCATA (API PLAY) ---
        # Usiamo 'card_selected' (quella scelta dall'utente), NON 'cid'
        card_payload = convert_id_to_payload(card_selected) 

        
        console.print(f"Gioco la carta: {fromid_to_card(card_selected)}...")
        # --- 5. GIOCATA (API PLAY) ---
        
        # Chiamata API POST /play
        play_result = asyncio.run( api_play_card(game_id, card_payload, CURRENT_USER_STATE))
        
        status = play_result.get("status") # waiting, resolved, finished, error
        
        if status == "error":
            console.print(f"[bold red]Errore mossa: {play_result.get('message')}[/]")
            time.sleep(2)
            continue # Riprova il turno
            
        # --- 6. GESTIONE RISPOSTA ---
        
        # CASO A: WAITING (Ho giocato per primo, aspetto l'altro)
        if status == "waiting":
            console.print(f"\n[bold yellow]In attesa della mossa dell'avversario...[/]")
            
            with console.status("L'avversario sta pensando...", spinner="dots"):
                # LOOP DI POLLING
                while True:
                    time.sleep(2) # Aspetta 2 secondi
                    
                    # Chiamo game/state per vedere se è cambiato qualcosa
                    check_state = asyncio.run(api_get_game_state(game_id, CURRENT_USER_STATE))
                    
                    if not check_state: continue
                    
                    new_turn = check_state.get("turn_number")
                    new_winner = check_state.get("winner")
                    
                    # CONDIZIONE DI USCITA: Il turno è avanzato o la partita è finita
                    if new_turn > current_turn or new_winner is not None:
                        
                        # --- CALCOLO VINCITORE DEL ROUND APPENA CONCLUSO ---
                        new_scores = check_state.get("scores", {})
                        
                        # Calcolo differenza punti
                        old_my = scores.get(my_username, 0)
                        new_my = new_scores.get(my_username, 0)
                        
                        old_opp = scores.get(opponent_name, 0)
                        new_opp = new_scores.get(opponent_name, 0)
                        
                        delta_my = new_my - old_my
                        delta_opp = new_opp - old_opp
                        
                        # Messaggio di riepilogo round
                        console.print("\n--------------------------------")
                        if delta_my > 0:
                            console.print(f"[bold green]L'avversario ha giocato. HAI VINTO IL ROUND! (+{delta_my} punti)[/]")
                        elif delta_opp > 0:
                            console.print(f"[bold red]L'avversario ha giocato. {opponent_name} VINCE IL ROUND. (+{delta_opp} punti)[/]")
                        else:
                            console.print(f"[bold white]Round terminato in pareggio (o nessun punto assegnato).[/]")
                        
                        # Pausa per leggere il risultato prima che il clear() pulisca lo schermo
                        time.sleep(3)
                        break 
            
            # Quando esce dal loop, il 'while True' principale ricomincerà
            # e scaricherà il nuovo stato aggiornato per mostrarlo.
            continue 

        # CASO B: RESOLVED (Ho giocato per secondo, turno finito)
        elif status == "resolved":
            # L'altro ha già giocato. Dobbiamo solo ricaricare il loop principale.
            # Il loop principale chiamerà game/state all'inizio e aggiornerà punteggi e turno.
            message = play_result.get("message", "Turno completato.")
            console.print(f"[green]{message}[/]")
            time.sleep(1.5) # Breve pausa per leggere
            continue 

        # CASO C: FINISHED (Ho giocato l'ultima carta)
        elif status == "finished":
            # La partita è finita. Ricarichiamo il loop principale un'ultima volta
            # All'inizio del loop, il controllo "if winner:" intercetterà la vittoria
            # e mostrerà la schermata finale.
            continue

def schermata_partita(console: Console, CURRENT_USER_STATE: UserState):
    console.clear()
    console.print("[bold blue]--- LOBBY MATCHMAKING ---[/]")

    # --- FASE 1: Selezione del Deck ---
    console.print("Caricamento dei tuoi deck...")
    
    # Chiamata API per ottenere i deck
    result = asyncio.run(api_get_deck_collection(CURRENT_USER_STATE))
    decks = result.get('data', []) if result and result.get('success') else []

    if not decks:
        console.print("[bold red]Non hai nessun deck! Crea un mazzo in Decks prima di giocare.[/]")
        questionary.text("Premi Invio per tornare indietro...").ask()
        return

    # Creazione menu di scelta (Slot: Nome)
    deck_choices = []
    deck_map = {} # Mappa label -> SLOT (non più ID)

    # Ordina per slot
    for deck in sorted(decks, key=lambda x: x.get('slot', 0)):
        slot = deck.get('slot')
        name = deck.get('name', 'Senza Nome')
        
        label = f"Slot {slot}: {name}"
        deck_choices.append(label)
        
        # 🟢 MODIFICA QUI: Salviamo lo slot come valore
        deck_map[label] = slot

    deck_choices.append("Annulla")

    scelta = questionary.select(
        "Con quale deck vuoi scendere in campo?",
        choices=deck_choices
    ).ask()

    if scelta == "Annulla" or scelta is None:
        return

    # Recuperiamo lo slot selezionato
    selected_deck_slot = deck_map[scelta]

    # --- FASE 2: Unirsi alla Coda ---
    console.print(f"\nTentativo di connessione alla lobby con il Deck nello slot {selected_deck_slot}...")
    
    # 🟢 MODIFICA QUI: Passiamo lo slot alla funzione API
    join_response = asyncio.run(api_join_matchmaking(selected_deck_slot, CURRENT_USER_STATE))
    print(join_response)
    if not join_response.get('success'):
        console.print(f"[bold red]Errore durante il join: {join_response.get('detail')}[/]")
        time.sleep(3)
        return
    
    if join_response.get('data')["status"] == "waiting":

        console.print("[green]Sei in coda! In attesa di un avversario...[/]")

        # --- FASE 3: Polling (Attesa attiva con animazione) ---
        game_found_data = None
        
        try:
            with console.status("[bold yellow]Ricerca avversario in corso...[/]", spinner="dots") as status:
                
                while True:
                    # 1. Chiamata API Status
                    match_status = asyncio.run(api_get_match_status(CURRENT_USER_STATE))
                    print(match_status)
                    if match_status:
                        state = match_status.get("status")
                        
                        if state == "matched" :
                            game_found_data = match_status
                            console.print("[bold green]Avversario Trovato![/]")
                            break 
                        
                        elif state == "waiting":
                            pass
                        
                        else:
                            console.print(f"[red]Stato sconosciuto o errore: {state}[/]")
                            return
                    
                    # 2. Attesa
                    time.sleep(2)

        except KeyboardInterrupt:
            console.print("\n[bold red]Matchmaking annullato dall'utente.[/]")
            return
    
    elif join_response.get('data')["status"] == "matched":
        game_found_data = join_response.get('data')

    # --- FASE 4: Avvio Partita ---
    if game_found_data:
        game_id = game_found_data.get("game_id")
        console.print(f"[bold white]Partita iniziata! ID: {game_id}[/]")
        gamescreen(console, game_id, CURRENT_USER_STATE)
        time.sleep(2)
        
        # await gioca_partita(console, game_id, CURRENT_USER_STATE)