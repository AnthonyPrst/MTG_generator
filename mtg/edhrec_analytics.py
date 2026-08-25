"""Analytics EDHRec - Popularité et power level des commandants."""

import json
import time
from typing import Dict, Optional, List, Any
import requests
import logging
from dataclasses import dataclass

from mtg.scryfall_http import SCRYFALL_HEADERS

logger = logging.getLogger(__name__)


@dataclass
class CommanderStats:
    """Statistiques d'un commandant sur EDHRec."""
    name: str
    edhrec_rank: Optional[int] = None
    num_decks: Optional[int] = None
    synergy_score: Optional[float] = None  # Score de synergie avec le deck
    staples_count: int = 0  # Nombre de staples dans le deck
    power_level: Optional[float] = None  # Score 1-10


class EDHRecAnalytics:
    """Récupère et analyse les données EDHRec pour les commandants."""
    
    EDHREC_API_BASE = "https://edhrec.com/api"
    SCRYFALL_SEARCH = "https://api.scryfall.com/cards/search"
    
    # Staples EDHRec (cartes très jouées, rank < 100)
    STAPLE_RANK_THRESHOLD = 500
    # Cartes très fortes (tutors, mana crypt, etc.)
    HIGH_POWER_RANK_THRESHOLD = 100
    
    def __init__(self):
        self._cache: Dict[str, Dict] = {}
    
    def _normalize_name(self, name: str) -> str:
        """Normalise le nom pour EDHRec."""
        # Remplacer espaces et caractères spéciaux
        return name.lower().replace(' ', '-').replace(',', '').replace("'", "")
    
    def get_commander_data(self, commander_name: str) -> Optional[Dict]:
        """Récupère les données EDHRec d'un commandant.
        
        Args:
            commander_name: Nom du commandant
        
        Returns:
            Données EDHRec ou None
        """
        if commander_name in self._cache:
            return self._cache[commander_name]
        
        try:
            # Utiliser Scryfall pour obtenir l'oracle_id, puis EDHRec
            time.sleep(0.1)
            search_url = f"https://api.scryfall.com/cards/named"
            params = {"exact": commander_name}
            response = requests.get(search_url, params=params, headers=SCRYFALL_HEADERS, timeout=30)
            response.raise_for_status()
            card_data = response.json()
            
            # Récupérer le edhrec_rank
            edhrec_rank = card_data.get('edhrec_rank')
            
            result = {
                'name': commander_name,
                'edhrec_rank': edhrec_rank,
                'oracle_id': card_data.get('oracle_id'),
                'type_line': card_data.get('type_line', ''),
                'mana_cost': card_data.get('mana_cost', ''),
                'cmc': card_data.get('cmc', 0),
            }
            
            self._cache[commander_name] = result
            return result
            
        except Exception as e:
            logger.warning(f"Impossible de récupérer les données EDHRec pour {commander_name}: {e}")
            return None
    
    def get_commander_tier(self, edhrec_rank: Optional[int]) -> str:
        """Détermine le tier d'un commandant basé sur son rang EDHRec.
        
        Args:
            edhrec_rank: Rang EDHRec (plus petit = plus populaire)
        
        Returns:
            Tier du commandant (S, A, B, C, D)
        """
        if edhrec_rank is None:
            return "?"
        
        if edhrec_rank <= 50:
            return "S (Top 50)"
        elif edhrec_rank <= 100:
            return "A (Top 100)"
        elif edhrec_rank <= 300:
            return "B (Populaire)"
        elif edhrec_rank <= 600:
            return "C (Joué)"
        else:
            return "D (Niche)"
    
    # Cartes cEDH / High Power connues (noms exacts en minuscules)
    CEDH_STAPLES = {
        # Fast mana
        'sol ring', 'mana crypt', 'mana vault', 'chrome mox', 'mox diamond',
        'lotus petal', 'grim monolith', 'basalt monolith', 'mox opal',
        'jeweled lotus', 'lions eye diamond', 'dark ritual', 'cabal ritual',
        'pyretic ritual', 'desperate ritual', 'rite of flame',
        # Tutors
        'demonic tutor', 'vampiric tutor', 'imperial seal', 'mystical tutor',
        'enlightened tutor', 'worldly tutor', 'gamble', 'personal tutor',
        'diabolic intent', 'grim tutor', 'wishclaw talisman', 'scheming symmetry',
        'finale of devastation', 'green suns zenith', 'chord of calling',
        'eldritch evolution', 'neoform', 'birthing pod',
        # Interaction efficace
        'force of will', 'force of negation', 'fierce guardianship', 'pact of negation',
        'mental misstep', 'swan song', 'flusterstorm', 'dispel', 'spell pierce',
        'dovin\'s veto', 'counterspell', 'mana drain', 'deflecting swat',
        'deadly rollick', 'swords to plowshares', 'path to exile',
        'abrupt decay', 'assassin\'s trophy', 'nature\'s claim', 'chain of vapor',
        # Draw/Avantage
        'rhystic study', 'mystic remora', 'necropotence', 'ad nauseam',
        'peer into the abyss', 'sylvan library', 'dark confidant',
        'esper sentinel', 'smothering tithe', 'dockside extortionist',
        # Combos / Win cons
        'thassa\'s oracle', 'demonic consultation', 'tainted pact',
        'underworld breach', 'brain freeze', 'grinding station',
        'isochron scepter', 'dramatic reversal', 'aetherflux reservoir',
        'walking ballista', 'heliod, sun-crowned', 'mikaeus, the unhallowed',
        'triskelion', 'kiki-jiki, mirror breaker', 'splinter twin',
        'thoracle', 'consultation',
    }
    
    # Cartes High Power (pas cEDH mais fortes)
    HIGH_POWER_CARDS = {
        'arcane signet', 'fellwar stone', 'thought vessel', 'mind stone',
        'signets', 'talismans', 'cultivate', 'kodama\'s reach',
        'cyclonic rift', 'toxic deluge', 'blasphemous act', 'vandalblast',
        'teferi\'s protection', 'heroic intervention', 'flawless maneuver',
        'lightning greaves', 'swiftfoot boots', 'skullclamp',
        'sensei\'s divining top', 'scroll rack',
    }

    def calculate_deck_power_level(
        self,
        deck_cards: List[Dict[str, Any]],
        commander_name: str
    ) -> Dict[str, Any]:
        """Calcule le power level d'un deck (échelle 1-10).
        
        Algorithme basé sur:
        - Présence de staples cEDH (tutors, fast mana, combos)
        - Présence de cartes high power
        - CMC moyen du deck (récupéré via types/role si absent)
        - Courbe de mana (% de cartes < 3 CMC)
        - Densité d'interaction
        
        Args:
            deck_cards: Liste des cartes du deck
            commander_name: Nom du commandant
        
        Returns:
            Dict avec power_level (1-10), tier, details
        """
        if not deck_cards:
            return {
                'power_level': 1,
                'staples_count': 0,
                'high_power_count': 0,
                'cmc_average': 0,
                'tier': 'N/A',
                'details': 'Deck vide'
            }
        
        cedh_count = 0
        high_power_count = 0
        total_cmc = 0
        cmc_counted = 0
        low_cmc_count = 0  # cartes avec CMC <= 2
        interaction_count = 0
        tutor_count = 0
        fast_mana_count = 0
        
        # Mots-clés pour détecter les rôles
        interaction_roles = {'removal', 'counterspell', 'interaction', 'boardwipe', 'wipe'}
        ramp_roles = {'ramp', 'mana'}
        
        for card in deck_cards:
            name = card.get('name', '').lower()
            role = str(card.get('role', '')).lower()
            types = str(card.get('types', '')).lower()
            cmc = card.get('cmc')
            
            # Estimer CMC si absent (basé sur le type)
            if cmc is None:
                if 'land' in types:
                    cmc = 0
                elif any(r in role for r in ramp_roles):
                    cmc = 2  # Les ramp sont généralement 2-3 CMC
                else:
                    cmc = 3  # Estimation par défaut
            
            total_cmc += cmc
            cmc_counted += 1
            if cmc <= 2:
                low_cmc_count += 1
            
            # Détecter les staples cEDH
            if name in self.CEDH_STAPLES:
                cedh_count += 1
                # Sous-catégories
                if 'tutor' in name or name in {'demonic consultation', 'tainted pact', 'finale of devastation'}:
                    tutor_count += 1
                if any(x in name for x in ['mana', 'mox', 'lotus', 'crypt', 'vault', 'ritual', 'monolith']):
                    fast_mana_count += 1
            
            # Détecter les cartes high power
            elif name in self.HIGH_POWER_CARDS or any(hp in name for hp in ['signet', 'talisman']):
                high_power_count += 1
            
            # Détecter l'interaction par rôle
            if any(r in role for r in interaction_roles):
                interaction_count += 1
        
        cmc_average = total_cmc / cmc_counted if cmc_counted > 0 else 3.0
        low_cmc_ratio = low_cmc_count / len(deck_cards) if deck_cards else 0
        
        # === Algorithme de scoring ===
        # Base: 4 (deck moyen)
        score = 4.0
        
        # Bonus staples cEDH (max +4)
        if cedh_count >= 15:
            score += 4.0
        elif cedh_count >= 10:
            score += 3.0
        elif cedh_count >= 6:
            score += 2.0
        elif cedh_count >= 3:
            score += 1.0
        elif cedh_count >= 1:
            score += 0.5
        
        # Bonus cartes high power (max +1.5)
        if high_power_count >= 10:
            score += 1.5
        elif high_power_count >= 5:
            score += 1.0
        elif high_power_count >= 2:
            score += 0.5
        
        # Bonus tutors (max +1)
        if tutor_count >= 5:
            score += 1.0
        elif tutor_count >= 3:
            score += 0.5
        
        # Bonus fast mana (max +1)
        if fast_mana_count >= 5:
            score += 1.0
        elif fast_mana_count >= 3:
            score += 0.5
        
        # Ajustement CMC (max ±1)
        if cmc_average <= 2.0:
            score += 1.0
        elif cmc_average <= 2.5:
            score += 0.5
        elif cmc_average >= 4.0:
            score -= 1.0
        elif cmc_average >= 3.5:
            score -= 0.5
        
        # Bonus courbe basse (max +0.5)
        if low_cmc_ratio >= 0.5:
            score += 0.5
        
        # Clamp 1-10
        power_level = max(1.0, min(10.0, score))
        
        # Déterminer le tier
        if power_level >= 9:
            tier = "cEDH"
        elif power_level >= 7.5:
            tier = "High Power"
        elif power_level >= 6:
            tier = "Optimized"
        elif power_level >= 4.5:
            tier = "Focused"
        elif power_level >= 3:
            tier = "Casual"
        else:
            tier = "Jank"
        
        return {
            'power_level': round(power_level, 1),
            'staples_count': cedh_count,
            'high_power_count': high_power_count,
            'cmc_average': round(cmc_average, 2),
            'fast_mana_count': fast_mana_count,
            'tutor_count': tutor_count,
            'tier': tier,
            'details': f"{cedh_count} cEDH staples, {tutor_count} tutors, {fast_mana_count} fast mana, CMC {cmc_average:.1f}"
        }
    
    def get_commander_popularity_text(self, commander_name: str) -> str:
        """Génère un texte descriptif de la popularité du commandant.
        
        Args:
            commander_name: Nom du commandant
        
        Returns:
            Texte formaté avec rang et tier
        """
        data = self.get_commander_data(commander_name)
        if not data:
            return "Données EDHRec non disponibles"
        
        rank = data.get('edhrec_rank')
        tier = self.get_commander_tier(rank)
        
        if rank:
            return f"Rang EDHRec: #{rank} - Tier {tier}"
        else:
            return f"Tier {tier}"
