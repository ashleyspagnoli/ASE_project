# --- HELPER FUNCTIONS PER LA VISUALIZZAZIONE ---

RANK_ORDER = {
    'A': 1, '2': 2, '3': 3, '4': 4, '5': 5, 
    '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 
    'J': 11, 'Q': 12, 'K': 13
}

SUIT_MAP = {'h': '❤️', 'd': '♦️', 'c': '♣️', 's': '♠️'}

def get_card_visual(card_id):
    """Converte 'h2' in '2 ❤️'"""
    if card_id == "JOKER":
        return "🃏 JOKER"
    
    suit_char = card_id[0]
    rank = card_id[1:]
    suit_emoji = SUIT_MAP.get(suit_char, '?')
    return f"{rank} {suit_emoji}"

def stampa_deck_visuale(console, cards_ids):
    """
    Prende la lista di ID ['h2', 'sK'] e la stampa ordinata per seme
    """
    if not cards_ids:
        console.print("[italic dim]Questo deck è vuoto.[/]")
        return

    # 1. Raggruppa per seme
    suits_data = {'h': [], 'd': [], 'c': [], 's': [], 'JOKER': []}
    
    for cid in cards_ids:
        if cid == "JOKER":
            suits_data['JOKER'].append(cid)
        else:
            if cid[0] in suits_data:
                suits_data[cid[0]].append(cid)

    # 2. Funzione di ordinamento (Key)
    def sort_key(cid):
        return RANK_ORDER.get(cid[1:], 0)

    # 3. Stampa riga per riga
    display_order = [('h', 'Cuori'), ('d', 'Quadri'), ('c', 'Fiori'), ('s', 'Picche')]
    
    console.print(f"[bold underline]Contenuto del Deck ({len(cards_ids)} carte):[/]")
    
    for suit_char, suit_name in display_order:
        cards = sorted(suits_data[suit_char], key=sort_key)
        if cards:
            # Crea la stringa visiva: "A ❤️  2 ❤️  K ❤️"
            row_str = "  ".join([get_card_visual(cid) for cid in cards])
            console.print(f"{row_str}")
            
    if suits_data['JOKER']:
        console.print("  ".join([get_card_visual(cid) for cid in suits_data['JOKER']]))
    
    console.print("") # Riga vuota finale