"""Gestion de la collection de cartes Magic: The Gathering."""

import sqlite3
import csv
import json

from typing import Tuple
from pathlib import Path
from typing import List, Dict, Optional, Any, Set
import logging
from mtg import constants as cts
from mtg.external_data import ExternalDataProvider
from mtg.import_formats import get_import_format, detect_format, get_available_formats
from mtg.scryfall_sync import ScryfallSyncManager

logger = logging.getLogger(__name__)

class CollectionManager:
    """Gère la collection de cartes Magic: The Gathering dans une base SQLite.

    Attributes:
        csv_path: Chemin vers le fichier CSV source
        db_path: Chemin vers la base de données SQLite
        collection_type: Type de collection ('physical' ou 'mtg_arena')
    """

    def __init__(self, collection_type: str = 'physical'):
        """Initialise le gestionnaire de collection.

        Args:
            collection_type: Type de collection ('physical' ou 'mtg_arena')
        """
        self.collection_type = collection_type
        self.csv_path = None
        self._last_skipped_count = 0
        if cts.CSV_PATH:
            self.csv_path = Path(cts.CSV_PATH)

        # Choisir la base de données selon le type de collection
        if collection_type == 'mtg_arena':
            if cts.MTGArena_DB_PATH:
                self.db_path = Path(cts.MTGArena_DB_PATH)
            else:
                self.db_path = Path("data/mtg_arena_collection.db")
        else:
            if cts.DB_PATH:
                self.db_path = Path(cts.DB_PATH)
            else:
                self.db_path = Path("data/collection.db")

        self.conn: Optional[sqlite3.Connection] = None
        self._scryfall_sync: Optional[ScryfallSyncManager] = None

        # Créer le répertoire de la base de données si nécessaire
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialiser la base de données
        self._init_db()

        # Si la base est vide et que c'est la collection physique, importer le CSV
        if self.collection_type == 'physical' and self._is_db_empty() and self.csv_path:
            raise FileNotFoundError(f"La base de données est vide")

    def _init_db(self) -> None:
        """Initialise la structure de la base de données si elle n'existe pas."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    colors TEXT,
                    types TEXT,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    scryfall_id TEXT,
                    oracle_id TEXT,
                    set_code TEXT,
                    set_name TEXT,
                    collector_number TEXT,
                    image_url TEXT,
                    foil INTEGER DEFAULT 0,
                    rarity TEXT,
                    card_condition TEXT,
                    language TEXT,
                    UNIQUE(name, scryfall_id)
                )
            """)
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Retourne une connexion à la base de données.
        
        Returns:
            Une connexion SQLite
        """
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def _is_db_empty(self) -> bool:
        """Vérifie si la base de données est vide.
        
        Returns:
            True si la base est vide, False sinon
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM cards")
            return cursor.fetchone()["count"] == 0

    def _load_csv_into_db(self, import_type: str, progress_cb=None, label_cb=None, bulk_provider=None) -> int:
        """Charge les données du CSV dans la base de données SQLite.

        Args:
            import_type: Type d'import ('ManaBox - Collection', 'Moxfield', 'CardNexus', etc.)
            progress_cb: Fonction de callback pour mettre à jour la barre de progression
            label_cb: Fonction de callback pour mettre à jour le label de progression
            bulk_provider: ScryfallSyncManager optionnel pour lookup local (évite les appels API)

        Returns:
            Nombre de cartes ignorées (skipped)
        """
        # Récupérer le format d'import
        import_format = get_import_format(import_type)
        if not import_format:
            raise ValueError(f"Format d'import non supporté : {import_type}")

        with (
            open(self.csv_path, 'r', encoding='utf-8') as csvfile,
            self._get_connection() as conn
        ):
            reader = csv.DictReader(csvfile)

            # Valider les colonnes requises
            import_format.validate_columns(reader.fieldnames)

            cursor = conn.cursor()
            cursor.execute("SELECT LOWER(name) as name, scryfall_id FROM cards")
            existing_cards: Set[tuple[str, str]] = {
                (row["name"], (row["scryfall_id"] or "").strip()) for row in cursor.fetchall()
            }
            inserted_count = 0
            skipped_count = 0

            # Compter le nombre de lignes pour le suivi de progression
            total_rows = 0
            try:
                csvfile.seek(0)
                reader = csv.DictReader(csvfile)
                total_rows = sum(1 for _ in reader)
                csvfile.seek(0)
                reader = csv.DictReader(csvfile)
            except Exception:
                total_rows = 0

            current_row = 0
            self.external_data_priovider = ExternalDataProvider()
            try:
                cursor.execute(
                    """
                    SELECT DISTINCT LOWER(TRIM(set_name)) as set_name, LOWER(TRIM(set_code)) as set_code
                    FROM cards
                    WHERE TRIM(COALESCE(set_name, '')) != ''
                      AND TRIM(COALESCE(set_code, '')) != ''
                    """
                )
                local_set_map = {
                    row["set_name"]: row["set_code"]
                    for row in cursor.fetchall()
                    if row["set_name"] and row["set_code"]
                }
                self.external_data_priovider.seed_set_code_cache(local_set_map)
            except Exception:
                pass

            # Traiter chaque ligne avec le format approprié
            for row in reader:
                current_row += 1
                if label_cb:
                    label_cb(f"Import {import_format.name} ({current_row}/{total_rows or '?'})")

                try:
                    # Traiter la ligne avec le format d'import
                    card_data = import_format.process_row(row, self.external_data_priovider, bulk_provider=bulk_provider)

                    # Vérifier si la carte existe déjà
                    key = (card_data['name'].lower(), card_data['scryfall_id'])
                    if key in existing_cards and card_data['scryfall_id']:
                        continue

                    # Insérer la carte dans la base de données
                    cursor.execute("""
                        INSERT OR IGNORE INTO cards
                        (name, colors, types, scryfall_id, oracle_id, set_code, set_name, collector_number, image_url,
                            foil, rarity, quantity, card_condition, language)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        card_data['name'],
                        card_data['colors'],
                        card_data['types'],
                        card_data['scryfall_id'],
                        card_data['oracle_id'],
                        card_data['set_code'],
                        card_data['set_name'],
                        card_data['collector_number'],
                        card_data['image_url'],
                        card_data['foil'],
                        card_data['rarity'],
                        card_data['quantity'],
                        card_data['card_condition'],
                        card_data['language']
                    ))

                    inserted_count += cursor.rowcount
                    if card_data['scryfall_id']:
                        existing_cards.add(key)

                    if progress_cb and total_rows:
                        progress_cb(current_row)

                except ValueError as e:
                    # Carte ignorée intentionnellement (ex: nom invalide)
                    skipped_count += 1
                    logger.warning(f"Carte ignorée ligne {current_row}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Erreur lors du traitement de la ligne {current_row}: {e}")
                    continue

            conn.commit()
            logger.info(f"Collection chargée depuis {self.csv_path} : {inserted_count} nouvelles cartes, {skipped_count} ignorées")

            return skipped_count

    def get_all_cards(self) -> List[Dict[str, Any]]:
        """Récupère toutes les cartes de la collection.
        
        Returns:
            Une liste de dictionnaires représentant les cartes
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cards ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    def _merge_card_rows(self, rows: List[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        """Fusionne plusieurs impressions d'une même carte en une vue agrégée."""
        if not rows:
            return None

        merged = dict(rows[0])
        merged["quantity"] = sum(int((row["quantity"] or 0)) for row in rows)

        for field in (
            "scryfall_id",
            "oracle_id",
            "set_code",
            "set_name",
            "collector_number",
            "image_url",
            "rarity",
            "colors",
            "types",
            "card_condition",
            "language",
        ):
            if merged.get(field):
                continue
            for row in rows[1:]:
                if row[field]:
                    merged[field] = row[field]
                    break

        return merged

    def find_cards_by_name(self, name: str) -> List[Dict[str, Any]]:
        """Retourne toutes les impressions correspondant à un nom exact."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cards WHERE LOWER(name) = LOWER(?) ORDER BY id",
                (name.strip(),)
            )
            return [dict(row) for row in cursor.fetchall()]

    def find_card_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Recherche une carte par son nom exact (insensible à la casse).
        
        Args:
            name: Le nom de la carte à rechercher
            
        Returns:
            Un dictionnaire représentant la carte, ou None si non trouvée
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cards WHERE LOWER(name) = LOWER(?) ORDER BY id",
                (name.strip(),)
            )
            return self._merge_card_rows(cursor.fetchall())

    def find_card_by_scryfallID(self, scryfall_id: str) -> Optional[Dict[str, Any]]:
        """Recherche une carte par son scryfall id.
        
        Args:
            name: Le scryfall id de la carte
            
        Returns:
            Un dictionnaire représentant la carte, ou None si non trouvée
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cards WHERE scryfall_id = ?",
                [scryfall_id]
            )
            result = cursor.fetchone()
            return dict(result) if result else None

    def find_card_by_oracleID(self, oracle_id: str) -> Optional[Dict[str, Any]]:
        """Recherche une carte par son oracle id.
        
        Args:
            name: l'oracle id de la carte
            
        Returns:
            Un dictionnaire représentant la carte, ou None si non trouvée
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cards WHERE oracle_id = ? ORDER BY id",
                [oracle_id]
            )
            return self._merge_card_rows(cursor.fetchall())

    def search_cards(self, query: str) -> List[Dict[str, Any]]:
        """Recherche des cartes par nom (recherche partielle insensible à la casse).
        
        Args:
            query: Le terme de recherche
            
        Returns:
            Une liste de dictionnaires représentant les cartes correspondantes
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM cards WHERE LOWER(name) LIKE LOWER(?)",
                (f"%{query.strip()}%",)
            )
            return [dict(row) for row in cursor.fetchall()]

    def _get_owned_card_names(self) -> Set[str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT LOWER(TRIM(name)) AS name
                FROM cards
                WHERE COALESCE(quantity, 0) > 0
                  AND TRIM(COALESCE(name, '')) != ''
                """
            )
            return {row["name"] for row in cursor.fetchall() if row["name"]}

    def _get_scryfall_sync(self) -> ScryfallSyncManager:
        if self._scryfall_sync is None:
            self._scryfall_sync = ScryfallSyncManager()
        return self._scryfall_sync

    @staticmethod
    def _is_commander_candidate_from_bulk(card: Dict[str, Any]) -> bool:
        games = card.get("games") or []
        if games and "paper" not in games:
            return False

        legality = str((card.get("legalities") or {}).get("commander") or "").lower()
        if legality in {"not_legal", "banned"}:
            return False

        type_lines = [
            str(card.get("face_type_line") or "").lower(),
            str(card.get("type_line") or "").lower(),
        ]
        oracle_texts = [
            str(card.get("face_oracle_text") or "").lower(),
            str(card.get("oracle_text") or "").lower(),
        ]

        for face in card.get("card_faces") or []:
            type_lines.append(str(face.get("type_line") or "").lower())
            oracle_texts.append(str(face.get("oracle_text") or "").lower())

        if any("legendary" in type_line and "creature" in type_line for type_line in type_lines):
            return True

        if any("legendary enchantment" in type_line and "background" in type_line for type_line in type_lines):
            return True

        if any("legendary artifact" in type_line and "vehicle" in type_line for type_line in type_lines):
            return True

        if any("legendary artifact" in type_line and "spacecraft" in type_line for type_line in type_lines):
            return True

        commander_markers = (
            "can be your commander",
            "can be a commander",
            "can serve as your commander",
        )
        return any(marker in oracle_text for oracle_text in oracle_texts for marker in commander_markers)

    def _get_commander_candidates_from_bulk(self) -> List[Dict[str, Any]]:
        try:
            scryfall_sync = self._get_scryfall_sync()
            if not scryfall_sync.is_bulk_available():
                return []
            cards = scryfall_sync.load_oracle_cards()
            owned_names = self._get_owned_card_names()
        except Exception as exc:
            logger.warning("Impossible de charger les candidats commandants depuis le bulk Scryfall: %s", exc)
            return []

        seen = set()
        candidates = []
        for card in cards.values():
            if not self._is_commander_candidate_from_bulk(card):
                continue

            name = str(card.get("name") or "").strip()
            if not name:
                continue

            key = name.lower()
            if key in seen:
                continue

            seen.add(key)
            candidate = dict(card)
            candidate["in_collection"] = key in owned_names
            candidates.append(candidate)

        candidates.sort(key=lambda row: (not bool(row.get("in_collection")), row["name"]))
        return candidates

    def get_commander_candidates(self, get_all: bool = False) -> List[Dict[str, Any]]:
        """Récupère les cartes pouvant être des commandants.
        
        Returns:
            Une liste de dictionnaires représentant les cartes légendaires de type créature
        """
        unique_rows = self._get_commander_candidates_from_bulk()
        if unique_rows:
            if get_all:
                return unique_rows
            return [row['name'] for row in unique_rows]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM cards 
                WHERE LOWER(types) LIKE '%legendary%' 
                  AND LOWER(types) LIKE '%creature%'
                ORDER BY name
            """)
            rows = cursor.fetchall()
            seen = set()
            unique_rows = []
            for row in rows:
                name = row['name']
                key = name.lower().strip()
                if key in seen:
                    continue
                seen.add(key)
                row_dict = dict(row)
                row_dict["in_collection"] = True
                unique_rows.append(row_dict)

            if get_all:
                return unique_rows
            else:
                return [row['name'] for row in unique_rows]

    def get_card_quantity(self, name: str) -> int:
        """Récupère la quantité d'une carte dans la collection.
        
        Args:
            name: Le nom de la carte
            
        Returns:
            La quantité disponible (0 si la carte n'existe pas)
        """
        card = self.find_card_by_name(name)
        return card['quantity'] if card else 0
    
    def get_card_colors(self, name: str) -> Set[str]:
        """Récupère l'identité couleur d'une carte.
        
        Args:
            name: Le nom de la carte
            
        Returns:
            Un ensemble de lettres représentant les couleurs de la carte.
            
        Comportement particulier pour les commandants non présents dans la collection :
            - Si la carte n'est pas trouvée en base locale, on interroge Scryfall
              via ``ExternalDataProvider`` pour récupérer son identité couleur.
            - En cas d'échec (erreur réseau, carte introuvable, etc.), on
              retourne un ensemble vide, ce qui laisse le deckbuilder gérer
              la situation (identité couleur considérée comme inconnue).
        """
        card = self.find_card_by_name(name)
        if card is not None:
            import ast
            colors = ast.literal_eval(card.get("colors", []))
            normalized_colors = {
                str(color).strip().upper()
                for color in colors
                if str(color).strip()
                and str(color).strip().lower() != "colorless"
            }
            return normalized_colors

        # Pas dans la collection locale : tentative via Scryfall
        try:
            provider = ExternalDataProvider()
            data = provider.get_scryfall_data(name)
        except Exception:
            # En cas de problème d'accès à Scryfall, on considère la carte
            # comme incolore / identité inconnue pour ne pas bloquer.
            return set()

        # On récupère l'identité couleur (color_identity est la bonne notion
        # pour Commander), en tombant éventuellement sur une carte incolore.
        colors = data.get("color_identity") or []
        return set(colors)

    def has_card(self, name: str) -> bool:
        """Vérifie si une carte est présente dans la collection.
        
        Args:
            name: Le nom de la carte
            
        Returns:
            True si la quantité est > 0, False sinon
        """
        return self.get_card_quantity(name) > 0

    def export_db_to_csv(self, path: str) -> None:
        """Exporte la base de données vers un fichier CSV.
        
        Args:
            path: Chemin du fichier de sortie
            
        Raises:
            IOError: En cas d'erreur d'écriture
        """
        try:
            cards = self.get_all_cards()
            if not cards:
                logger.warning("Aucune carte à exporter")
                return
                
            with open(path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['name', 'colors', 'types', 'quantity', 'scryfall_id', 'set_code', 'set_name', 'collector_number', 'foil', 'rarity', 'card_condition', 'language']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for card in cards:
                    writer.writerow({
                        'name': card['name'],
                        'colors': card.get('colors', ''),
                        'types': card.get('types', ''),
                        'quantity': card['quantity'],
                        'scryfall_id': card.get('scryfall_id', ''),
                        'set_code': card.get('set_code', ''),
                        'set_name': card.get('set_name', ''),
                        'collector_number': card.get('collector_number', ''),
                        'foil': card.get('foil', 0),
                        'rarity': card.get('rarity', ''),
                        'card_condition': card.get('card_condition', ''),
                        'language': card.get('language', '')
                    })
                    
            logger.info(f"Collection exportée avec succès vers {path}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'export CSV : {str(e)}")
            raise

    def export_db_list_cards_to_txt(self, scryfall_id_list: list[str], path: str) -> None:
        """Exporte une liste de cartes vers un fichier texte.

        Chaque carte correspondant aux ``scryfall_id`` fournis est écrite sur une
        ligne, au format lisible par un joueur (par exemple ``3x Sol Ring [C15-235]``).

        Args:
            scryfall_id_list: Liste d'identifiants Scryfall (oracle_id ou id de carte).
            path: Chemin du fichier texte de sortie.

        Raises:
            IOError: En cas d'erreur d'écriture du fichier.
        """
        if not scryfall_id_list:
            logger.warning("Liste de scryfall_id vide, rien à exporter")
            return

        # Récupération des cartes concernées depuis la base
        placeholders = ",".join(["?"] * len(scryfall_id_list))
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM cards WHERE cards.scryfall_id IN ({placeholders}) ORDER BY cards.name",
                scryfall_id_list,
            )
            cards = [dict(row) for row in cursor.fetchall()]

        if not cards:
            logger.warning("Aucune carte trouvée pour les scryfall_id fournis")
            return

        try:
            with open(path, "w", encoding="utf-8") as txtfile:
                for card in cards:
                    qty = card.get("quantity", 1)
                    name = card.get("name", "?")
                    set_code = card.get("set_code", "")
                    collector = card.get("collector_number", "")

                    # Format type : "3x Sol Ring (C15) 235"
                    if set_code and collector:
                        line = f"{1}x {name} ({set_code}) {collector}\n"
                    else:
                        line = f"{1}x {name}\n"
                    txtfile.write(line)

            logger.info(f"Liste de cartes exportée avec succès vers {path}")
        except Exception as e:
            logger.error(f"Erreur lors de l'export TXT : {str(e)}")
            raise

    def clear_all_cards(self) -> None:
        """Supprime toutes les cartes de la collection."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cards")
            conn.commit()

    def __del__(self):
        """Ferme la connexion à la base de données lors de la destruction de l'instance."""
        if hasattr(self, 'conn'):
            self.conn.close()

    # Méthodes de compatibilité avec l'ancienne interface
    def load_from_csv(self, csv_path: str, import_type: str = None, progress_cb=None, label_cb=None, bulk_provider=None) -> bool:
        """Charge la collection depuis un fichier CSV.

        Args:
            csv_path: Chemin vers le fichier CSV de collection.
            import_type: Type d'import (si None, détection automatique)
            progress_cb: Fonction de callback pour la progression
            label_cb: Fonction de callback pour le label
            bulk_provider: ScryfallSyncManager optionnel pour lookup local (évite les appels API)

        Returns:
            bool: True si le chargement a réussi, False sinon.
        """
        try:
            cts.CSV_PATH = csv_path
            self.csv_path = Path(csv_path)

            # Détection automatique du format si non spécifié
            if import_type is None:
                detected_format = detect_format(csv_path)
                if detected_format:
                    import_type = detected_format.name
                    logger.info(f"Format détecté automatiquement : {import_type}")
                else:
                    raise ValueError("Impossible de détecter automatiquement le format du fichier. Veuillez spécifier le format d'import.")

            skipped = self._load_csv_into_db(import_type, progress_cb, label_cb, bulk_provider=bulk_provider)
            # Stocker le nombre de cartes ignorées pour affichage ultérieur
            self._last_skipped_count = skipped
            return True
        except Exception as e:
            logger.error(f"Erreur lors du chargement du CSV : {str(e)}")
            return False

    def get_card(self, card_name: str) -> Optional[dict]:
        """Récupère les informations d'une carte par son nom (compatibilité).
        
        Args:
            card_name: Nom de la carte à rechercher.
            
        Returns:
            dict: Informations de la carte, ou None si non trouvée.
        """
        return self.find_card_by_name(card_name)


    def compare_deck_to_collection(self, deck_data: dict) -> list[dict]:
        """
        Compare un deck Archidekt à la collection locale.

        Args:
            deck_data: JSON complet retourné par l'API Archidekt.
            collection: Instance de CollectionManager.

        Returns:
            Liste de dicts : chaque entrée décrit la disponibilité d'une carte.
        """
        results = []
        oracle_in_db = True
        for name, info in deck_data.items():
            oracle_id = info["oracle_id"]
            quantity_needed = info["quantity"]

            owned_quantity = 0
            card_local = None

            # 1. Essai par scryfall_id
            if oracle_id and oracle_in_db:
                try:
                    card_local = self.find_card_by_oracleID(oracle_id)
                except sqlite3.OperationalError:
                    oracle_in_db = False

            # 2. Sinon essai par nom
            if card_local is None:
                card_local = self.find_card_by_name(name)

            if card_local:
                owned_quantity = card_local["quantity"]
                types = card_local["types"]
                defaultCategory = info["defaultCategory"]
                if defaultCategory is None:
                    if 'Land' in types:
                        defaultCategory = "Land"
                    else:
                        defaultCategory = "Other"

                results.append({
                    "name": name,
                    "colors": card_local["colors"],
                    "types": card_local["types"],
                    "scryfall_id": card_local["scryfall_id"],
                    "image_url": card_local["image_url"],
                    "edhrec_rank": info["edhrec_rank"],
                    "occurence": info["occurence"],
                    "defaultCategory": defaultCategory,
                    "needed": quantity_needed,
                    "owned": owned_quantity,
                    "missing": max(0, quantity_needed - owned_quantity),
                    # Données supplémentaires pour filtres
                    "set_code": card_local.get("set_code", ""),
                    "set_name": card_local.get("set_name", ""),
                    "collector_number": card_local.get("collector_number", ""),
                    "rarity": card_local.get("rarity", ""),
                })

        return results
