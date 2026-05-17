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
        self._set_code_cache: dict[str, str] = {}
        self._set_catalog_loaded: bool = False

        self._cache_dir = Path(__file__).parent.parent / "data" / "scryfall"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._set_code_cache_file = self._cache_dir / "set_code_cache.json"
        self._load_set_code_cache_from_disk()

    def _load_set_code_cache_from_disk(self) -> None:
        if not self._set_code_cache_file.exists():
            return

        try:
            with open(self._set_code_cache_file, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                return

            normalized: dict[str, str] = {}
            for key, value in payload.items():
                key_norm = str(key or "").strip().lower()
                value_norm = str(value or "").strip().lower()
                if key_norm and value_norm:
                    normalized[key_norm] = value_norm

            if normalized:
                self._set_code_cache.update(normalized)
                self._set_catalog_loaded = True
        except Exception:
            return

    def _save_set_code_cache_to_disk(self) -> None:
        try:
            with open(self._set_code_cache_file, "w", encoding="utf-8") as handle:
                json.dump(self._set_code_cache, handle, ensure_ascii=False, indent=2)
        except Exception:
            return

    def seed_set_code_cache(self, mapping: Dict[str, str]) -> None:
        changed = False
        for key, value in (mapping or {}).items():
            key_norm = str(key or "").strip().lower()
            value_norm = str(value or "").strip().lower()
            if not key_norm or not value_norm:
                continue
            if self._set_code_cache.get(key_norm) == value_norm:
                continue
            self._set_code_cache[key_norm] = value_norm
            changed = True

        if changed:
            self._save_set_code_cache_to_disk()

    @staticmethod
    def _extract_image_url_from_card_data(data: dict) -> Optional[str]:
        if not data:
            return None

        if "image_uris" in data:
            urls = data["image_uris"]
            return urls.get("normal") or urls.get("large") or urls.get("png")

        faces = data.get("card_faces")
        if faces:
            for face in faces:
                urls = face.get("image_uris")
                if urls:
                    return urls.get("normal") or urls.get("large") or urls.get("png")

        return None

    def _load_set_catalog(self) -> None:
        if self._set_catalog_loaded:
            return

        set_map: dict[str, str] = {}
        next_url = "https://api.scryfall.com/sets"

        try:
            while next_url:
                time.sleep(0.075)
                response = requests.get(next_url, timeout=20)
                response.raise_for_status()
                payload = response.json()

                for item in payload.get("data", []):
                    code = str(item.get("code") or "").strip().lower()
                    name = str(item.get("name") or "").strip().lower()
                    if code:
                        set_map[code] = code
                    if name and code:
                        set_map[name] = code

                next_url = payload.get("next_page") if payload.get("has_more") else None
        except requests.exceptions.RequestException:
            pass

        if set_map:
            self._set_code_cache.update(set_map)
            self._save_set_code_cache_to_disk()
        self._set_catalog_loaded = True

    def resolve_set_code(self, set_code: str = "", set_name: str = "") -> str:
        raw_code = str(set_code or "").strip().lower()
        if raw_code:
            return raw_code

        raw_name = str(set_name or "").strip().lower()
        if not raw_name:
            return ""

        if raw_name in self._set_code_cache:
            return self._set_code_cache[raw_name]

        self._load_set_catalog()
        return self._set_code_cache.get(raw_name, "")

    def get_card_for_exact_print(self, set_code: str = "", collector_number: str = "", set_name: str = "") -> Optional[Dict]:
        resolved_set_code = self.resolve_set_code(set_code=set_code, set_name=set_name)
        collector_number = (collector_number or "").strip()
        if not resolved_set_code or not collector_number:
            return None

        cache_key = f"print::{resolved_set_code}::{collector_number}"
        data = self._scryfall_cache.get(cache_key)
        if data is not None:
            return data

        try:
            time.sleep(0.075)
            url = f"https://api.scryfall.com/cards/{resolved_set_code}/{collector_number}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            self._scryfall_cache[cache_key] = data
            return data
        except requests.exceptions.RequestException:
            return None

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

    def get_scryfall_data(self, identifier: str, set_code: str = None, collector_number: str = None):
        """Récupère les informations d'une carte depuis l'API Scryfall.

        Args:
            identifier: Soit un ``scryfall_id`` (UUID), soit un nom exact de
                carte.
            set_code: Code de l'extension (ex: 'DSK') pour une recherche précise.
            collector_number: Numéro de collection pour une recherche précise.

        Returns:
            dict: les informations complètes de la carte telles que renvoyées
            par Scryfall.
        """
        if identifier and identifier.startswith("cardnexus::"):
            return None

        cache_key = f"{identifier}_{set_code}_{collector_number}" if set_code and collector_number else identifier
        if cache_key in self._scryfall_cache:
            return self._scryfall_cache[cache_key]

        try:
            # Déterminer si l'identifiant ressemble à un UUID Scryfall
            is_uuid_like = len(identifier) in (32, 36) and all(c in "0123456789abcdef-" for c in identifier.lower())

            time.sleep(0.075)
            if is_uuid_like:
                url = f"https://api.scryfall.com/cards/{identifier}"
                response = requests.get(url)
            elif set_code and collector_number:
                # Recherche par set et numéro (plus précise)
                url = f"https://api.scryfall.com/cards/{set_code.lower()}/{collector_number}"
                response = requests.get(url)
            else:
                # Recherche par nom exact
                url = "https://api.scryfall.com/cards/named"
                params = {"exact": identifier}
                response = requests.get(url, params=params)

            response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP
            card_data = response.json()
            self._scryfall_cache[cache_key] = card_data
            return card_data

        except requests.exceptions.RequestException as e:
            # Fallback sur la recherche par nom si la recherche par set/numéro échoue
            if set_code and collector_number:
                logger.warning(f"Recherche précise échouée pour {identifier} ({set_code}/{collector_number}), tentative par nom seul...")
                return self.get_scryfall_data(identifier)
            
            logger.error(f"Erreur lors de l'appel à l'API Scryfall : {str(e)}")
            raise ValueError(f"Impossible de récupérer les informations de la carte : {str(e)}")
        except (KeyError, ValueError) as e:
            logger.error(f"Format de réponse inattendu de l'API Scryfall : {str(e)}")
            raise ValueError("Format de réponse inattendu de l'API Scryfall")

    def get_image_url_from_scryfall(self, scryfall_id: str) -> Optional[str]:
        """Retourne l'URL d'image (format normal) pour une carte donnée."""
        if scryfall_id and scryfall_id.startswith("cardnexus::"):
            return None
        data = self.get_scryfall_data(scryfall_id)
        return self._extract_image_url_from_card_data(data)

    def get_image_url_for_exact_print(self, set_code: str, collector_number: str, set_name: str = "") -> Optional[str]:
        """Retourne l'URL d'image pour une impression précise (set + collector number).

        Utilise un endpoint Scryfall strict sans fallback par nom.
        """
        data = self.get_card_for_exact_print(
            set_code=set_code,
            collector_number=collector_number,
            set_name=set_name,
        )
        return self._extract_image_url_from_card_data(data)

    def get_card_cmc(self, scryfall_id: str) -> Optional[float]:
        """Retourne le coût converti de mana (cmc) d'une carte depuis Scryfall (cache)."""
        if not scryfall_id or scryfall_id.startswith("cardnexus::"):
            return None
        data = self.get_scryfall_data(scryfall_id)
        if not data:
            return None
        try:
            return float(data.get("cmc")) if data.get("cmc") is not None else None
        except (TypeError, ValueError):
            return None


