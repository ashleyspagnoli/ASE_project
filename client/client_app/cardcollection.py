import questionary
import asyncio
import time
from client_app.apicalls import api_get_card_collection, api_get_deck_collection, api_create_deck
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


def deck_creation_screen(console:Console,CURRENT_USER_STATE: UserState):
    """Schermata per la creazione di un nuovo deck."""
    console.clear()
    console.print("[bold blue]--- DECK CREATION PAGE ---[/]")
    # Qui puoi aggiungere ulteriori logiche per la creazione del deck
    sceltaslot=questionary.select(
        "Select the slot to save the new deck:",
        choices=['1','2','3','4','5','cancel'],
    ).ask()
    if sceltaslot == 'cancel':
        return
    sceltanome=questionary.text(
        "Enter the name of the new deck (or type 'cancel' to go back):"
    ).ask()
    suites=['hearts ❤️','diamonds ♦️','clubs ♣️','spades ♠️', 'cancel']
    cards=['2','3','4','5','6','7','8','9','10','J','Q','K','A','cancel']
    deck=[]
    for i in suites:
        sceltasuite=questionary.select(
            "Select the suit for the deck:",
            choices=suites,
        ).ask()

        if sceltasuite == 'hearts ❤️':
            selected_suite='h'
        elif sceltasuite == 'diamonds ♦️':
            selected_suite='d'
        elif sceltasuite == 'clubs ♣️':
            selected_suite='c'
        elif sceltasuite == 'spades ♠️':
            selected_suite='s'
        elif sceltasuite == 'cancel':
            return
        
        scelta=questionary.select(
            "Select the card for the deck:",
            choices=cards,
        ).ask()

        if scelta == cards[0]:
            selected_card='2'
            cardid1=selected_suite + selected_card
            cardid2=selected_suite + cards[11]
            console.print(f"Added cards: {fromid_to_card(cardid1)} and {fromid_to_card(cardid2)}")
            time.sleep(1)
        elif scelta == cards[1]:
            selected_card='3'
            cardid1=selected_suite + selected_card
            cardid2=selected_suite + cards[10]
            console.print(f"Added cards: {fromid_to_card(cardid1)} and {fromid_to_card(cardid2)}")
            time.sleep(1)
        elif scelta == cards[2]:
            selected_card='4'
            cardid1=selected_suite + selected_card
            cardid2=selected_suite + cards[9]
            console.print(f"Added cards: {fromid_to_card(cardid1)} and {fromid_to_card(cardid2)}")
            time.sleep(1)
        elif scelta == cards[3]:
            selected_card='5'
            cardid1=selected_suite + selected_card
            cardid2=selected_suite + cards[8]
            console.print(f"Added cards: {fromid_to_card(cardid1)} and {fromid_to_card(cardid2)}")
            time.sleep(1)
        elif scelta == cards[4]:
            selected_card='6'
            cardid1=selected_suite + selected_card
            cardid2=selected_suite + cards[7]
            console.print(f"Added cards: {fromid_to_card(cardid1)} and {fromid_to_card(cardid2)}")
            
            time.sleep(1)
        elif scelta == cards[5]:
            selected_card='7'
            cardid1=selected_suite + selected_card
            cardid2=selected_suite + cards[6]
            console.print(f"Added cards: {fromid_to_card(cardid1)} and {fromid_to_card(cardid2)}")
            time.sleep(1)
        elif scelta == cards[6]:
            selected_card='8'
            cardid1=selected_suite + selected_card
            scelta2=questionary.select(
                f"Select the second card for the suite:{selected_suite}",
                choices=['A','7'], 
            ).ask()
            cardid2=selected_suite + scelta2
            console.print(f"Added cards: {fromid_to_card(cardid1)} and {fromid_to_card(cardid2)}")
            time.sleep(1)
        elif scelta == cards[7]:
            selected_card='9'
            cardid1=selected_suite + selected_card
            cardid2=selected_suite + cards[4]
            console.print(f"Added cards: {fromid_to_card(cardid1)} and {fromid_to_card(cardid2)}")
            time.sleep(1)
        elif scelta == cards[8]:
            selected_card='10'
            cardid1=selected_suite + selected_card
            cardid2=selected_suite + cards[3]
            console.print(f"Added cards: {fromid_to_card(cardid1)} and {fromid_to_card(cardid2)}")
            time.sleep(1)
        elif scelta == cards[9]:
            selected_card='J'
            cardid1=selected_suite + selected_card
            cardid2=selected_suite + cards[2]
            console.print(f"Added cards: {fromid_to_card(cardid1)} and {fromid_to_card(cardid2)}")
            time.sleep(1)
        elif scelta == cards[10]:
            selected_card='Q'
            cardid1=selected_suite + selected_card
            cardid2=selected_suite + cards[1]
            console.print(f"Added cards: {fromid_to_card(cardid1)} and {fromid_to_card(cardid2)}")
            time.sleep(1)
        elif scelta == cards[11]:
            selected_card='K'
            cardid1=selected_suite + selected_card
            cardid2=selected_suite + cards[0]
            console.print(f"Added cards: {fromid_to_card(cardid1)} and {fromid_to_card(cardid2)}")
            time.sleep(1)
        elif scelta == cards[12]:
            selected_card='A'
            cardid1=selected_suite + selected_card
            cardid2=selected_suite + '8'
            console.print(f"Added cards: {fromid_to_card(cardid1)} and {fromid_to_card(cardid2)}")
            time.sleep(1)

        elif scelta == 'cancel':
            return
        deck.append(cardid1)
        deck.append(cardid2)
        print(deck)
        suites.remove(sceltasuite)

    console.print(f"Deck created with cards: {deck}")
    response = asyncio.run(api_create_deck(deck=deck,deck_name=sceltanome,deck_slot=sceltaslot,CURRENT_USER_STATE=CURRENT_USER_STATE))
    console.print(response.message)
    



        


def deck_screen(console:Console,CURRENT_USER_STATE: UserState):
    """Mostra la schermata del deck."""
    console.clear()
    console.print("[bold blue]--- DECK PAGE ---[/]")
    scelta=questionary.select(
        "What do you want to do?",
        choices=["View Decks", "Create Deck", "Go Back"],
    ).ask()
    if scelta == "Go Back":
        return
    elif scelta == "View Decks":
        console.print(asyncio.run(api_get_deck_collection(CURRENT_USER_STATE=CURRENT_USER_STATE)))
        time.sleep(5)
    elif scelta == "Create Deck":
        deck_creation_screen(console,CURRENT_USER_STATE)
        time.sleep(2)


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
            console.print("[bold blue]--- CARD COLLECTION ---[/]")
            """
            data = response.json()
            return data  # Ritorna i dati della card collection
            nella richiesta API ora ritorniamo un oggetto ApiResponse
            """

            result = asyncio.run(api_get_card_collection(CURRENT_USER_STATE=CURRENT_USER_STATE))
            cards_list: List[Dict[str, str]] = result.get('data', [])
            console.print(result)
            console.print("[bold yellow]--- Card Collection ---[/]")
            previoussuite=""
            for card in cards_list:
                    card=card.get("id")
                    
                    #Prendi il primo carattere dell'id della carta per identificare il seme
                    if card[0]!=previoussuite:
                        console.print("\n")
                        previoussuite=card[0]

                    #Le carte dello stesso seme vengono stampate nella stessa riga
                    console.print(fromid_to_card(card))
                    
            questionary.text("Press Enter to continue...").ask()
        
        elif scelta is "Deck Page":
            deck_screen(console,CURRENT_USER_STATE)
        


