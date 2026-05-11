"""Synchronisation incrémentale des données Scryfall Bulk Data."""

import json
import gzip
import time
from pathlib import Path
from typing import Dict, Optional, List, Any
import requests
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ScryfallSyncManager:
    """Gère la synchronisation des bulk data Scryfall.
    
    Scryfall fournit plusieurs types de bulk data:
    - default-cards : Toutes les cartes avec prints
    - oracle-cards : Une carte par oracle ID (meilleur pour les recherches)
    - unique-artwork : Une entrée par artwork unique
    - all-cards : Toutes les cartes de tous les prints
    
    On utilise 'oracle-cards' pour les recherches par nom et 'default-cards' pour
    les données complètes incluant les prix et disponibilité.
    """
    
    BULK_API_URL = "https://api.scryfall.com/bulk-data"
    _NON_PLAYABLE_LAYOUTS = {
        "art_series",
        "token",
        "double_faced_token",
        "emblem",
        "augment",
        "host",
        "planar",
        "scheme",
        "vanguard",
    }
    _NON_PLAYABLE_SET_TYPES = {"memorabilia", "token", "minigame"}
    
    def __init__(self, data_dir: Optional[Path] = None):
        """Initialise le gestionnaire de synchronisation.
        
        Args:
            data_dir: Répertoire de stockage des données. Par défaut: data/scryfall/
        """
        if data_dir is None:
            self.data_dir = Path(__file__).parent.parent / "data" / "scryfall"
        else:
            self.data_dir = Path(data_dir)
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache_info_file = self.data_dir / "cache_info.json"
        self.oracle_cards_file = self.data_dir / "oracle-cards.json"
        self.default_cards_file = self.data_dir / "default-cards.json"
        
        self._oracle_cards_cache: Optional[Dict[str, Any]] = None
        self._default_cards_cache: Optional[Dict[str, Any]] = None
        self._cards_by_scryfall_id: Optional[Dict[str, Any]] = None
    
    def _load_cache_info(self) -> Dict:
        """Charge les informations de cache."""
        if self.cache_info_file.exists():
            try:
                with open(self.cache_info_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}
    
    def _save_cache_info(self, info: Dict):
        """Sauvegarde les informations de cache."""
        with open(self.cache_info_file, 'w', encoding='utf-8') as f:
            json.dump(info, f, indent=2)
    
    def _get_bulk_data_info(self) -> Optional[Dict]:
        """Récupère les métadonnées des bulk data depuis Scryfall."""
        try:
            time.sleep(0.1)  # Rate limiting
            response = requests.get(self.BULK_API_URL, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Erreur récupération bulk data info: {e}")
            return None
    
    def _download_file(self, url: str, destination: Path, progress_callback=None) -> bool:
        """Télécharge un fichier avec support du gzip.
        
        Args:
            url: URL du fichier à télécharger
            destination: Chemin de destination
            progress_callback: Fonction callback(percent, downloaded_bytes, total_bytes, speed_mbps, message)
        
        Returns:
            True si succès, False sinon
        """
        import time as time_module
        
        try:
            time.sleep(0.1)  # Rate limiting
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 256 * 1024  # 256KB chunks - petit pour mises à jour fréquentes
            start_time = time_module.time()
            last_update_time = start_time
            
            with open(destination, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        current_time = time_module.time()
                        # Mettre à jour le callback toutes les 0.5 secondes ou à 100%
                        if progress_callback:
                            elapsed = current_time - start_time
                            speed = (downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                            
                            if total_size > 0:
                                percent = int((downloaded / total_size) * 100)
                            else:
                                percent = -1  # Indéterminé
                            
                            if (current_time - last_update_time >= 0.5) or percent >= 100:
                                progress_callback(percent, downloaded, total_size, speed, "")
                                last_update_time = current_time
            
            return True
        except Exception as e:
            logger.error(f"Erreur téléchargement {url}: {e}")
            if destination.exists():
                destination.unlink()
            return False
    
    def needs_update(self, max_age_days: int = 7) -> bool:
        """Vérifie si une mise à jour est nécessaire.
        
        Args:
            max_age_days: Âge maximum du cache en jours
        
        Returns:
            True si mise à jour nécessaire
        """
        cache_info = self._load_cache_info()
        
        if not self.oracle_cards_file.exists():
            return True
        
        last_update_str = cache_info.get('last_update')
        if not last_update_str:
            return True
        
        try:
            last_update = datetime.fromisoformat(last_update_str)
            if datetime.now() - last_update > timedelta(days=max_age_days):
                return True
        except Exception:
            return True
        
        # Vérifier aussi la version remote
        bulk_info = self._get_bulk_data_info()
        if not bulk_info:
            return False  # Pas de connexion, on garde le cache
        
        remote_updated_at = None
        for item in bulk_info.get('data', []):
            if item.get('type') == 'oracle_cards':
                remote_updated_at = item.get('updated_at')
                break
        
        if remote_updated_at:
            local_updated_at = cache_info.get('remote_updated_at')
            if local_updated_at != remote_updated_at:
                return True
        
        return False
    
    def sync(self, progress_callback=None, force: bool = False) -> bool:
        """Synchronise les données Scryfall.
        
        Args:
            progress_callback: Fonction callback(percent, downloaded_bytes, total_bytes, speed_mbps, message)
            force: Force la mise à jour même si le cache est récent
        
        Returns:
            True si succès
        """
        logger.info(f"Sync démarrée (force={force})")
        
        if not force and not self.needs_update():
            if progress_callback:
                progress_callback(100, 0, 0, 0, "Cache à jour - Pas de mise à jour nécessaire")
            logger.info("Cache Scryfall à jour")
            return True
        
        logger.info("Mise à jour nécessaire, récupération des métadonnées...")
        if progress_callback:
            progress_callback(0, 0, 0, 0, "Récupération des métadonnées...")
        
        bulk_info = self._get_bulk_data_info()
        if not bulk_info:
            logger.error("Impossible de récupérer les métadonnées bulk")
            if progress_callback:
                progress_callback(-1, 0, 0, 0, "Erreur: Impossible de récupérer les métadonnées")
            return False
        
        logger.info(f"Métadonnées récupérées: {len(bulk_info.get('data', []))} types disponibles")
        
        # Trouver les URLs
        oracle_url = None
        default_url = None
        remote_updated_at = None
        
        for item in bulk_info.get('data', []):
            if item.get('type') == 'oracle_cards':
                oracle_url = item.get('download_uri')
                remote_updated_at = item.get('updated_at')
            elif item.get('type') == 'default_cards':
                default_url = item.get('download_uri')
        
        if not oracle_url:
            if progress_callback:
                progress_callback(-1, 0, 0, 0, "Erreur: URL oracle-cards non trouvée")
            return False
        
        # Wrapper pour adapter le callback
        def wrap_progress(percent, downloaded, total, speed, message):
            if progress_callback:
                progress_callback(percent, downloaded, total, speed, "")
        
        # Télécharger oracle-cards
        if progress_callback:
            progress_callback(0, 0, 0, 0, "Téléchargement Oracle Cards...")
        
        temp_oracle = self.data_dir / "oracle-cards.json.tmp"
        if not self._download_file(oracle_url, temp_oracle, wrap_progress):
            if progress_callback:
                progress_callback(-1, 0, 0, 0, "Erreur téléchargement Oracle Cards")
            return False
        
        # Renommer le fichier temporaire
        if self.oracle_cards_file.exists():
            self.oracle_cards_file.unlink()
        temp_oracle.rename(self.oracle_cards_file)
        
        # Note: default-cards (~500 MB) n'est pas téléchargé par défaut.
        # oracle-cards (~160 MB) suffit pour les recherches et synergies.
        
        # Sauvegarder les infos de cache
        cache_info = {
            'last_update': datetime.now().isoformat(),
            'remote_updated_at': remote_updated_at,
            'oracle_cards_size': self.oracle_cards_file.stat().st_size if self.oracle_cards_file.exists() else 0,
        }
        self._save_cache_info(cache_info)
        
        # Invalider les caches en mémoire
        self._oracle_cards_cache = None
        self._default_cards_cache = None
        self._cards_by_scryfall_id = None
        
        if progress_callback:
            progress_callback(100, 0, 0, 0, "Synchronisation terminée")
        
        logger.info("Synchronisation Scryfall terminée")
        return True
    
    def load_oracle_cards(self) -> Dict[str, Any]:
        """Charge les cartes oracle en mémoire.
        
        Returns:
            Dictionnaire {name_lower: card_data}
        """
        if self._oracle_cards_cache is not None:
            return self._oracle_cards_cache
        
        if not self.oracle_cards_file.exists():
            logger.warning("Fichier oracle-cards non trouvé, synchronisation nécessaire")
            return {}
        
        try:
            with open(self.oracle_cards_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Indexer par nom (lowercase pour recherche insensible)
            cards_by_name = {}
            for card in data:
                name = card.get('name', '').lower()
                if name:
                    # Enrichir avec des champs utiles pour l'app
                    enriched_card = self._enrich_card_data(card)
                    existing = cards_by_name.get(name)
                    if existing is None or self._get_lookup_preference_score(enriched_card) > self._get_lookup_preference_score(existing):
                        cards_by_name[name] = enriched_card
                # Faces doubles
                for face in card.get('card_faces', []):
                    face_name = face.get('name', '').lower()
                    if face_name and face_name != name:
                        enriched_face = self._enrich_card_data(card, face)
                        existing_face = cards_by_name.get(face_name)
                        if existing_face is None or self._get_lookup_preference_score(enriched_face) > self._get_lookup_preference_score(existing_face):
                            cards_by_name[face_name] = enriched_face
            
            self._oracle_cards_cache = cards_by_name
            
            # Construire aussi l'index par scryfall_id
            self._cards_by_scryfall_id = {}
            for card in data:
                sid = card.get('id', '')
                if sid:
                    self._cards_by_scryfall_id[sid] = card
            
            logger.info(f"{len(cards_by_name)} cartes oracle chargées ({len(self._cards_by_scryfall_id)} par scryfall_id)")
            return cards_by_name
        except Exception as e:
            logger.error(f"Erreur chargement oracle-cards: {e}")
            return {}

    def _get_lookup_preference_score(self, card: Dict) -> int:
        """Retourne un score de préférence pour les lookups par nom.

        Objectif: privilégier les vraies cartes jouables en évitant les entrées
        comme art_series/tokens qui peuvent partager le même nom.
        """
        score = 0

        layout = (card.get('layout') or '').lower()
        if layout in self._NON_PLAYABLE_LAYOUTS:
            score -= 100
        else:
            score += 20

        set_type = (card.get('set_type') or '').lower()
        if set_type in self._NON_PLAYABLE_SET_TYPES:
            score -= 60

        games = card.get('games') or []
        if 'paper' in games:
            score += 15

        type_line = card.get('type_line') or card.get('face_type_line') or ''
        if type_line.strip() and type_line.strip().lower() != 'card':
            score += 20

        if card.get('oracle_text') or card.get('face_oracle_text'):
            score += 10

        return score
    
    def _enrich_card_data(self, card: Dict, face: Optional[Dict] = None) -> Dict:
        """Enrichit les données de carte avec des champs dérivés utiles."""
        result = card.copy()
        
        if face:
            # Pour les faces doubles, prendre les données de la face
            result['face_name'] = face.get('name')
            result['face_oracle_text'] = face.get('oracle_text', '')
            result['face_mana_cost'] = face.get('mana_cost', '')
            result['face_type_line'] = face.get('type_line', '')
        
        # Texte oracle combiné (pour la recherche de synergies)
        oracle_text = result.get('oracle_text', '')
        if face and face.get('oracle_text'):
            oracle_text = face.get('oracle_text', '')
        
        # Combiner tous les textes pour la détection de synergies
        combined_text = f"{result.get('name', '')} {result.get('type_line', '')} {oracle_text}"
        result['_search_text'] = combined_text.lower()
        
        # Détecter les catégories de staples
        edhrec_rank = result.get('edhrec_rank')
        if edhrec_rank:
            if edhrec_rank < 100:
                result['_staple_tier'] = 'S'  # Staple universel
            elif edhrec_rank < 500:
                result['_staple_tier'] = 'A'  # Très joué
            elif edhrec_rank < 1000:
                result['_staple_tier'] = 'B'  # Populaire
            else:
                result['_staple_tier'] = 'C'
        
        return result
    
    def get_card_data(self, card_name: str) -> Optional[Dict]:
        """Récupère les données d'une carte par son nom.
        
        Args:
            card_name: Nom de la carte
        
        Returns:
            Données de la carte ou None
        """
        cards = self.load_oracle_cards()
        # Recherche exacte d'abord
        data = cards.get(card_name.lower())
        if data:
            return data
        
        # Recherche partielle
        name_lower = card_name.lower()
        for key, value in cards.items():
            if name_lower in key or key in name_lower:
                return value
        
        return None
    
    def search_cards_by_keyword(self, keyword: str) -> List[Dict]:
        """Recherche toutes les cartes contenant un mot-clé dans leur texte.
        
        Args:
            keyword: Mot-clé à chercher
        
        Returns:
            Liste des cartes correspondantes
        """
        cards = self.load_oracle_cards()
        keyword_lower = keyword.lower()
        results = []
        
        for card in cards.values():
            search_text = card.get('_search_text', '')
            if keyword_lower in search_text:
                results.append(card)
        
        return results
    
    def get_staples_list(self, tier: Optional[str] = None) -> List[Dict]:
        """Retourne la liste des staples (cartes très jouées).
        
        Args:
            tier: Filtrer par tier ('S', 'A', 'B') ou None pour tous
        
        Returns:
            Liste des staples
        """
        cards = self.load_oracle_cards()
        staples = []
        
        for card in cards.values():
            card_tier = card.get('_staple_tier')
            if card_tier:
                if tier is None or card_tier == tier:
                    staples.append(card)
        
        # Trier par edhrec_rank
        staples.sort(key=lambda c: c.get('edhrec_rank', 999999))
        return staples
    
    def get_card_synergy_score(self, card_name: str, synergies: List[str]) -> float:
        """Calcule un score de synergie pour une carte basé sur le bulk.
        
        Args:
            card_name: Nom de la carte
            synergies: Liste des mots-clés synergiques
        
        Returns:
            Score de synergie (0.0 - 1.0+)
        """
        card = self.get_card_data(card_name)
        if not card:
            return 0.0
        
        search_text = card.get('_search_text', '')
        if not search_text:
            return 0.0
        
        # Compter les correspondances
        matches = 0
        for synergy in synergies:
            if synergy.lower() in search_text:
                matches += 1
        
        # Score avec dégressivité
        if matches == 0:
            return 0.0
        elif matches == 1:
            return 0.15
        elif matches == 2:
            return 0.30
        else:
            return 0.45  # Max 45% bonus
    
    def get_card_for_import(self, scryfall_id: str = '', card_name: str = '') -> Optional[Dict]:
        """Récupère les données d'une carte pour l'import de collection.
        
        Utilise le bulk data local au lieu de l'API Scryfall.
        Cherche d'abord par scryfall_id (oracle bulk), puis par nom.
        
        Args:
            scryfall_id: ID Scryfall de la carte (printing spécifique)
            card_name: Nom de la carte en fallback
        
        Returns:
            Dict avec oracle_id, type_line, color_identity, image_uris ou None
        """
        # S'assurer que le cache est chargé
        self.load_oracle_cards()
        
        # 1. Chercher par scryfall_id (le bulk oracle a un seul print par carte)
        if scryfall_id and self._cards_by_scryfall_id:
            card = self._cards_by_scryfall_id.get(scryfall_id)
            if card:
                return card
        
        # 2. Chercher par nom
        if card_name and self._oracle_cards_cache:
            card = self._oracle_cards_cache.get(card_name.lower())
            if card:
                return card
        
        return None
    
    def is_bulk_available(self) -> bool:
        """Vérifie si le bulk data est disponible pour les lookups."""
        return self.oracle_cards_file.exists()

    def get_image_url(self, scryfall_id: str = '', card_name: str = '') -> Optional[str]:
        """Récupère l'URL d'image depuis le bulk data (sans appel API).
        
        Les images sont sur scryfall.io qui n'a PAS de rate limit.
        
        Args:
            scryfall_id: ID Scryfall de la carte
            card_name: Nom de la carte en fallback
            
        Returns:
            URL de l'image (format normal) ou None
        """
        card = self.get_card_for_import(scryfall_id, card_name)
        if not card:
            return None
        
        # Cartes simples
        if 'image_uris' in card:
            uris = card['image_uris']
            return uris.get('normal') or uris.get('large') or uris.get('png')
        
        # Cartes double-face
        faces = card.get('card_faces')
        if faces:
            for face in faces:
                uris = face.get('image_uris')
                if uris:
                    return uris.get('normal') or uris.get('large') or uris.get('png')
        
        return None
    
    def get_cache_status(self) -> Dict:
        """Retourne le statut du cache."""
        cache_info = self._load_cache_info()
        
        status = {
            'has_oracle_cards': self.oracle_cards_file.exists(),
            'has_default_cards': self.default_cards_file.exists(),
            'last_update': cache_info.get('last_update', 'Jamais'),
            'remote_updated_at': cache_info.get('remote_updated_at', 'Inconnu'),
            'oracle_cards_size_mb': 0,
        }
        
        if self.oracle_cards_file.exists():
            size_bytes = self.oracle_cards_file.stat().st_size
            status['oracle_cards_size_mb'] = round(size_bytes / (1024 * 1024), 2)
        
        return status
