"""Stratégies de deck prédéfinies et détection de synergies."""

from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from enum import Enum


class DeckStrategy(Enum):
    """Stratégies de deck prédéfinies pour Commander."""
    AGGRO = "Aggro"
    CONTROL = "Control"
    COMBO = "Combo"
    MIDRANGE = "Midrange"
    BUDGET = "Budget"


@dataclass
class StrategyProfile:
    """Profil de stratégie définissant les ratios cibles."""
    name: str
    ramp: int
    draw: int
    removal: int
    boardwipe: int
    wincon: int
    min_lands: int
    max_lands: int
    cmc_target: float  # CMC moyen visé
    description: str


# Profils de stratégies prédéfinis
STRATEGY_PROFILES: Dict[DeckStrategy, StrategyProfile] = {
    DeckStrategy.AGGRO: StrategyProfile(
        name="Aggro",
        ramp=8,
        draw=6,
        removal=6,
        boardwipe=2,
        wincon=8,
        min_lands=32,
        max_lands=35,
        cmc_target=2.5,
        description="Deck rapide avec créatures agressives et peu de terrains"
    ),
    DeckStrategy.CONTROL: StrategyProfile(
        name="Control",
        ramp=14,
        draw=14,
        removal=10,
        boardwipe=6,
        wincon=4,
        min_lands=38,
        max_lands=42,
        cmc_target=3.5,
        description="Deck contrôle avec beaucoup de réponses et de pioche"
    ),
    DeckStrategy.COMBO: StrategyProfile(
        name="Combo",
        ramp=14,
        draw=14,
        removal=6,
        boardwipe=4,
        wincon=8,  # Pieces du combo
        min_lands=34,
        max_lands=38,
        cmc_target=3.0,
        description="Deck combo avec accélération et pioche pour assembler les pieces"
    ),
    DeckStrategy.MIDRANGE: StrategyProfile(
        name="Midrange",
        ramp=10,
        draw=8,
        removal=8,
        boardwipe=4,
        wincon=6,
        min_lands=36,
        max_lands=38,
        cmc_target=3.2,
        description="Deck équilibré avec valeur à toutes les étapes de la partie"
    ),
    DeckStrategy.BUDGET: StrategyProfile(
        name="Budget",
        ramp=12,
        draw=10,
        removal=8,
        boardwipe=4,
        wincon=6,
        min_lands=36,
        max_lands=38,
        cmc_target=3.0,
        description="Deck utilisant uniquement cartes communes et peu communes"
    ),
}


# Mots-clés de synergies par mécanique
SYNERGY_KEYWORDS: Dict[str, List[str]] = {
    "sacrifice": ["sacrifice", "sacrifices", "sacrifie", "sacrificed"],
    "token": ["token", "tokens", "jeton", "jetons"],
    "graveyard": ["graveyard", "cemetery", "cimetière", "grave"],
    "discard": ["discard", "discards", "defausse", "defausser"],
    "counter": ["counter", "counters", "compteur", "compteurs"],
    "lifegain": ["life", "gains", "gagnez", "points de vie"],
    "flying": ["flying", "vol", "volante"],
    "trample": ["trample", "piétinement"],
    "haste": ["haste", "célérité"],
    "deathtouch": ["deathtouch", "contact mortel"],
    "lifelink": ["lifelink", "lien de vie"],
    "etb": ["enters", "arrive", "enter", "étb"],
    "dies": ["dies", "die", "meurt", "mort"],
    "attack": ["attacks", "attack", "attaque", "attaques"],
    "draw": ["draw", "draws", "pioche", "piocher", "pioché"],
    "mana": ["mana", "add", "ajoute", "produces"],
    "tutor": ["search", "library", "recherche", "bibliothèque"],
    "mill": ["mill", "mills", "moudre", "meule"],
    "artifact": ["artifact", "artifacts", "artefact", "artefacts"],
    "enchantment": ["enchantment", "enchantments", "enchantement"],
    "equipment": ["equipment", "equipments", "équipement"],
    "aura": ["aura", "auras"],
    "wizard": ["wizard", "wizards", "sorcier", "sorciers"],
    "goblin": ["goblin", "goblins", "gobelin", "gobelins"],
    "elf": ["elf", "elves", "elfe", "elfes"],
    "dragon": ["dragon", "dragons"],
    "zombie": ["zombie", "zombies"],
    " vampire": [" vampire", " vampires"],  # space to avoid "vampiric"
    "spirit": ["spirit", "spirits", "esprit", "esprits"],
}


class StrategyManager:
    """Gère les stratégies de deck et la détection de synergies."""
    
    def __init__(self, scryfall_sync=None):
        self.current_strategy = DeckStrategy.MIDRANGE
        self.budget_mode = False
        self.scryfall_sync = scryfall_sync  # Pour accès au bulk data
        
        # Cache des synergies détectées
        self._commander_synergies_cache: Dict[str, List[str]] = {}
        self._staples_cache: Optional[List[str]] = None
    
    def set_strategy(self, strategy: DeckStrategy) -> StrategyProfile:
        """Définit la stratégie active et retourne son profil."""
        self.current_strategy = strategy
        return STRATEGY_PROFILES[strategy]
    
    def set_budget_mode(self, enabled: bool):
        """Active ou désactive le mode budget."""
        self.budget_mode = enabled
    
    def get_strategy_params(self) -> Dict[str, int]:
        """Retourne les paramètres pour la stratégie active."""
        profile = STRATEGY_PROFILES[self.current_strategy]
        return {
            "ramp": profile.ramp,
            "draw": profile.draw,
            "removal": profile.removal,
            "boardwipe": profile.boardwipe,
            "wincon": profile.wincon,
            "min_lands": profile.min_lands,
            "max_lands": profile.max_lands,
        }
    
    def detect_commander_synergies(self, commander_data: Dict[str, Any]) -> List[str]:
        """Détecte les mécaniques synergiques du commandant.
        
        Args:
            commander_data: Données Scryfall du commandant
            
        Returns:
            Liste des mécaniques détectées
        """
        if not commander_data:
            return []
        
        synergies = []
        
        # Texte à analyser (nom + type + texte oracle)
        text_to_check = ""
        if "name" in commander_data:
            text_to_check += commander_data["name"] + " "
        if "type_line" in commander_data:
            text_to_check += commander_data["type_line"] + " "
        if "oracle_text" in commander_data:
            text_to_check += commander_data.get("oracle_text", "") + " "
        
        # Faces doubles
        for face in commander_data.get("card_faces", []):
            if "name" in face:
                text_to_check += face["name"] + " "
            if "type_line" in face:
                text_to_check += face["type_line"] + " "
            if "oracle_text" in face:
                text_to_check += face.get("oracle_text", "") + " "
        
        text_lower = text_to_check.lower()
        
        # Détecter les synergies
        for mechanic, keywords in SYNERGY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    synergies.append(mechanic)
                    break
        
        return list(set(synergies))  # Dédupliquer
    
    def score_card_synergy(
        self, 
        card_data: Dict[str, Any], 
        commander_synergies: List[str],
        base_score: float
    ) -> float:
        """Calcule un score de synergie pour une carte.
        
        Args:
            card_data: Données de la carte
            commander_synergies: Liste des synergies du commandant
            base_score: Score de base de la carte
            
        Returns:
            Score ajusté avec bonus de synergie
        """
        if not commander_synergies:
            return base_score
        
        # Texte de la carte
        text_to_check = ""
        if "name" in card_data:
            text_to_check += card_data["name"] + " "
        if "types" in card_data:
            text_to_check += str(card_data["types"]) + " "
        if "oracle_text" in card_data:
            text_to_check += str(card_data.get("oracle_text", "")) + " "
        
        text_lower = text_to_check.lower()
        
        # Compter les synergies
        synergy_matches = 0
        for synergy in commander_synergies:
            keywords = SYNERGY_KEYWORDS.get(synergy, [])
            for keyword in keywords:
                if keyword in text_lower:
                    synergy_matches += 1
                    break
        
        # Bonus de synergie: +15% par mécanique synergique
        if synergy_matches > 0:
            bonus = 1 + (0.15 * min(synergy_matches, 3))  # Max 45% bonus
            return base_score * bonus
        
        return base_score
    
    def is_budget_card(self, card_data: Dict[str, Any]) -> bool:
        """Vérifie si une carte est éligible en mode budget.
        
        Args:
            card_data: Données de la carte
            
        Returns:
            True si la carte est commune ou peu commune
        """
        if not self.budget_mode:
            return True
        
        rarity = card_data.get("rarity", "").lower()
        # En mode budget, on accepte uniquement common et uncommon
        return rarity in ["common", "uncommon", "", None]
    
    def get_strategy_description(self, strategy: Optional[DeckStrategy] = None) -> str:
        """Retourne la description d'une stratégie."""
        if strategy is None:
            strategy = self.current_strategy
        return STRATEGY_PROFILES[strategy].description
    
    def get_all_strategies(self) -> List[DeckStrategy]:
        """Retourne toutes les stratégies disponibles."""
        return list(DeckStrategy)
    
    def score_card_synergy_with_bulk(
        self,
        card_name: str,
        commander_synergies: List[str],
        base_score: float
    ) -> float:
        """Calcule un score de synergie utilisant le bulk Scryfall si disponible.
        
        Cette méthode est plus précise car elle utilise le texte Oracle complet
        du bulk data plutôt que les données partielles de la collection.
        
        Args:
            card_name: Nom de la carte
            commander_synergies: Liste des synergies du commandant
            base_score: Score de base
            
        Returns:
            Score ajusté
        """
        if not self.scryfall_sync or not commander_synergies:
            return base_score
        
        try:
            synergy_score = self.scryfall_sync.get_card_synergy_score(
                card_name, commander_synergies
            )
            if synergy_score > 0:
                return base_score * (1 + synergy_score)
        except Exception:
            pass
        
        return base_score
    
    def get_staples_for_strategy(self) -> List[str]:
        """Retourne la liste des staples recommandées pour la stratégie actuelle.
        
        Returns:
            Liste des noms de staples
        """
        if not self.scryfall_sync:
            return []
        
        if self._staples_cache is None:
            try:
                staples = self.scryfall_sync.get_staples_list(tier='S')
                self._staples_cache = [s.get('name') for s in staples[:50]]
            except Exception:
                return []
        
        return self._staples_cache
    
    def is_card_staple(self, card_name: str) -> bool:
        """Vérifie si une carte est un staple EDHRec.
        
        Args:
            card_name: Nom de la carte
            
        Returns:
            True si c'est un staple
        """
        if not self.scryfall_sync:
            return False
        
        try:
            card_data = self.scryfall_sync.get_card_data(card_name)
            if card_data:
                return card_data.get('_staple_tier') in ['S', 'A']
        except Exception:
            pass
        
        return False
    
    def get_card_recommendations(
        self,
        commander_name: str,
        synergy_type: str,
        count: int = 10
    ) -> List[Dict]:
        """Recommande des cartes basées sur le bulk Scryfall.
        
        Args:
            commander_name: Nom du commandant
            synergy_type: Type de synergie recherchée (ex: 'sacrifice', 'token')
            count: Nombre de recommandations
            
        Returns:
            Liste des cartes recommandées
        """
        if not self.scryfall_sync:
            return []
        
        try:
            # Rechercher les cartes avec ce mot-clé
            cards = self.scryfall_sync.search_cards_by_keyword(synergy_type)
            
            # Filtrer et trier par edhrec_rank
            results = []
            for card in cards:
                edhrec_rank = card.get('edhrec_rank')
                if edhrec_rank and edhrec_rank < 2000:  # Cartes jouées
                    results.append({
                        'name': card.get('name'),
                        'edhrec_rank': edhrec_rank,
                        'tier': card.get('_staple_tier', 'C'),
                        'type_line': card.get('type_line', ''),
                    })
            
            # Trier par rang et prendre les meilleures
            results.sort(key=lambda c: c['edhrec_rank'])
            return results[:count]
            
        except Exception as e:
            logger.error(f"Erreur recommandations: {e}")
            return []
