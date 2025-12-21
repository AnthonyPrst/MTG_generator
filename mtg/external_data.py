"""Gestion des données externes (Archidekt, Scryfall, etc.)."""

from typing import List, Dict, Optional, Tuple
import json
import time
import requests
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ExternalDataProvider:
    """Gère la récupération des données externes."""

    def __init__(self) -> None:
        self._scryfall_cache: dict[str, dict] = {}

    def get_archidekt_decks_id_for_commander(self, commander_name: str, order_by: str) -> list[str]:
        """Récupère les ids des decks archideckt en fonction d'un commandant spécifique.

        Args:
            commander_name (str): nom du commandant à filtrer

        Returns:
            list[str]: liste des ids de deck
        """
        if order_by == "Vues":
            order_by = "-viewCount"
        else:
            order_by = "-updatedAt"
        base = "https://archidekt.com/api/decks/v3/"
        params = {
            "commanderName": commander_name,
            "deckFormat": "3",
            "orderBy": order_by,
            "page": 1
        }
        r = requests.get(base, params=params)
        r.raise_for_status()
        results = r.json().get("results", [])
        decks_id = []
        if results:
            for result in results:
                decks_id.append(str(result["id"]))
        return decks_id
    
    def load_archidekt_deck(self, id: str) -> Dict:
        """Charge un deck exporté depuis Archidekt.
        
        Args:
            file_path: Chemin vers le fichier JSON d'Archidekt.
            
        Returns:
            dict: Structure du deck chargé.
        """
        base = f"https://archidekt.com/api/decks/{id}/cards/"
        r = requests.get(base)
        r.raise_for_status()
        results = r.json()
        cards= {}
        if results:
            for result in results:
                info = result["card"]
                card = info["oracleCard"]
                cards[card["name"]] = {"oracle_id": card["uid"], "quantity": result["quantity"], "edhrec_rank": card["edhrecRank"], "defaultCategory": card["defaultCategory"], "occurence": 1}
        return cards

    def get_scryfall_data(self, scryfall_id: str) -> Tuple[str, list]:
        """Récupère les informations d'une carte depuis l'API Scryfall.
        
        Args:
            scryfall_id: L'identifiant de la carte sur Scryfall
        
        Returns:
            les informations de la carte
        """
        if scryfall_id in self._scryfall_cache:
            return self._scryfall_cache[scryfall_id]

        try:
            # Appel à l'API Scryfall
            time.sleep(0.075)
            response = requests.get(f"https://api.scryfall.com/cards/{scryfall_id}")
            response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP
            card_data = response.json()
            self._scryfall_cache[scryfall_id] = card_data
            return card_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur lors de l'appel à l'API Scryfall : {str(e)}")
            raise ValueError(f"Impossible de récupérer les informations de la carte : {str(e)}")
        except (KeyError, ValueError) as e:
            logger.error(f"Format de réponse inattendu de l'API Scryfall : {str(e)}")
            raise ValueError("Format de réponse inattendu de l'API Scryfall")

    def get_image_url_from_scryfall(self, scryfall_id: str) -> Optional[str]:
        """Retourne l'URL d'image (format normal) pour une carte donnée."""
        data = self.get_scryfall_data(scryfall_id)
        if not data:
            return None

        # Cartes simples
        if "image_uris" in data:
            urls = data["image_uris"]
            return urls.get("normal") or urls.get("large") or urls.get("png")

        # Cartes double-face, split, etc.
        faces = data.get("card_faces")
        if faces:
            for face in faces:
                urls = face.get("image_uris")
                if urls:
                    return urls.get("normal") or urls.get("large") or urls.get("png")
        return None

    def get_card_cmc(self, scryfall_id: str) -> Optional[float]:
        """Retourne le coût converti de mana (cmc) d'une carte depuis Scryfall (cache)."""
        if not scryfall_id:
            return None
        data = self.get_scryfall_data(scryfall_id)
        if not data:
            return None
        try:
            return float(data.get("cmc")) if data.get("cmc") is not None else None
        except (TypeError, ValueError):
            return None


