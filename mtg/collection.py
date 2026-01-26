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

logger = logging.getLogger(__name__)

class CollectionManager:
    """Gère la collection de cartes Magic: The Gathering dans une base SQLite.
    
    Attributes:
        csv_path: Chemin vers le fichier CSV source
        db_path: Chemin vers la base de données SQLite
    """
    
    def __init__(self):
        """Initialise le gestionnaire de collection.
        """
        self.csv_path = None
        if cts.CSV_PATH:
            self.csv_path = Path(cts.CSV_PATH)
        if cts.DB_PATH:
            self.db_path = Path(cts.DB_PATH)
        self.conn: Optional[sqlite3.Connection] = None
        
        # Créer le répertoire de la base de données si nécessaire
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialiser la base de données
        self._init_db()
        
        # Si la base est vide, importer le CSV
        if self._is_db_empty() and self.csv_path:
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

    

    def _get_some_data_from_scryfall(self, scryfall_id: str) -> Tuple[str, list]:
        """Récupère les types et les couleurs d'une carte depuis l'API Scryfall.
        
        Args:
            scryfall_id: L'identifiant de la carte sur Scryfall
        
        Returns:
            Un tuple contenant (types, couleurs) de la carte
        """
        types, colors = None, None
        
        card_data = self.external_data_priovider.get_scryfall_data(scryfall_id)
        # Extraction des types et couleurs
        oracle_id = card_data.get('oracle_id', '')
        types = card_data.get('type_line', '')
        colors = card_data.get('color_identity', [])
        image = ''
        if "image_uris" in card_data:
            urls = card_data["image_uris"]
            image = urls.get("normal") or urls.get("large") or urls.get("png")

        # Cartes double-face, split, etc.
        faces = card_data.get("card_faces")
        if faces:
            for face in faces:
                urls = face.get("image_uris")
                if urls:
                    image = urls.get("normal") or urls.get("large") or urls.get("png")
        
        # Si pas de couleurs (artefact, terre, etc.)
        if not colors and 'Land' not in types:
            colors = ['colorless'] 
        return oracle_id, image, types, colors

    def _load_csv_into_db(self, import_type: str, progress_cb=None, label_cb=None) -> None:
        """Charge les données du CSV dans la base de données SQLite.
        
        Args:
            import_type: Type d'import ('ManaBox - Collection' ou 'Moxfield')
            progress_cb: Fonction de callback pour mettre à jour la barre de progression
            label_cb: Fonction de callback pour mettre à jour le label de progression
        """
        with (
            open(self.csv_path, 'r', encoding='utf-8') as csvfile,
            self._get_connection() as conn
        ):
            reader = csv.DictReader(csvfile)
            cursor = conn.cursor()

            cursor.execute("SELECT LOWER(name) as name, scryfall_id FROM cards")
            existing_cards: Set[tuple[str, str]] = {
                (row["name"], (row["scryfall_id"] or "").strip()) for row in cursor.fetchall()
            }
            inserted_count = 0
            
            # Vérifier les colonnes requises
            total_rows = 0
            # Compter le nombre de lignes pour le suivi de progression
            try:
                total_rows = sum(1 for _ in reader)
                csvfile.seek(0)
                reader = csv.DictReader(csvfile)
            except Exception:
                total_rows = 0

            current_row = 0

            if import_type == "ManaBox - Collection":
                required_columns = {'Name', 'Set code', 'Set name', 'Collector number', 
                                    'Foil', 'Rarity', 'Quantity', 'Scryfall ID', 'Condition', 'Language'}
                if not required_columns.issubset(reader.fieldnames or []):
                    raise ValueError(f"Le fichier ManaBox doit contenir les colonnes : {required_columns}")
                
                self.external_data_priovider = ExternalDataProvider()
                
                # Insérer uniquement les nouvelles données
                for row in reader:
                    current_row += 1
                    if label_cb:
                        label_cb(f"Import ManaBox ({current_row}/{total_rows or '?'})")
                    scryfall_id = row.get('Scryfall ID', '').strip()
                    key = (row['Name'].strip().lower(), scryfall_id)
                    if key in existing_cards:
                        continue
                    oracle_id, image, types, colors = self._get_some_data_from_scryfall(scryfall_id)
                    cursor.execute("""
                        INSERT OR IGNORE INTO cards 
                        (name, colors, types, scryfall_id, oracle_id, set_code, set_name, collector_number, image_url,
                            foil, rarity, quantity, card_condition, language)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row['Name'].strip(),
                        str(colors),
                        types,
                        scryfall_id,
                        oracle_id,
                        row.get('Set code', '').strip(),
                        row.get('Set name', '').strip(),
                        row.get('Collector number', '').strip(),
                        image,
                        1 if row.get('Foil', '').lower() == 'foil' else 0,
                        row.get('Rarity', '').strip(),
                        int(row.get('Quantity', 1)),
                        row.get('Condition', '').strip(),
                        row.get('Language', 'English').strip()
                    ))
                    inserted_count += cursor.rowcount
                    existing_cards.add(key)
                    if progress_cb and total_rows:
                        progress_cb(current_row)
                
            elif import_type == "Moxfield":
                required_columns = {'name', 'scryfall_id', 'colors', 'types', 'quantity'}
                if not required_columns.issubset(reader.fieldnames or []):
                    raise ValueError(f"Le fichier Moxfield doit contenir les colonnes : {required_columns}")
                
                for row in reader:
                    current_row += 1
                    if label_cb:
                        label_cb(f"Import Moxfield ({current_row}/{total_rows or '?'})")
                    scryfall_id = row.get('scryfall_id', '').strip()
                    key = (row['name'].strip().lower(), scryfall_id)
                    if key in existing_cards:
                        continue
                    cursor.execute("""
                        INSERT OR IGNORE INTO cards 
                        (name, scryfall_id, colors, types, quantity)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        row['name'].strip(),
                        scryfall_id,
                        row.get('colors', '').upper().strip(),
                        row.get('types', '').strip(),
                        int(row.get('quantity', 1))
                    ))
                    inserted_count += cursor.rowcount
                    existing_cards.add(key)
                    if progress_cb and total_rows:
                        progress_cb(current_row)
            else:
                raise ValueError(f"Type d'import non supporté : {import_type}")
            
            conn.commit()
            logger.info(f"Collection chargée depuis {self.csv_path} : {inserted_count} nouvelles cartes")

    def get_all_cards(self) -> List[Dict[str, Any]]:
        """Récupère toutes les cartes de la collection.
        
        Returns:
            Une liste de dictionnaires représentant les cartes
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cards ORDER BY name")
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
                "SELECT * FROM cards WHERE LOWER(name) = LOWER(?)",
                (name.strip(),)
            )
            result = cursor.fetchone()
            return dict(result) if result else None

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
                "SELECT * FROM cards WHERE oracle_id = ?",
                [oracle_id]
            )
            result = cursor.fetchone()
            return dict(result) if result else None

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

    def get_commander_candidates(self, get_all: bool = False) -> List[Dict[str, Any]]:
        """Récupère les cartes pouvant être des commandants.
        
        Returns:
            Une liste de dictionnaires représentant les cartes légendaires de type créature
        """
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
                unique_rows.append(dict(row))

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
            Un ensemble de lettres représentant les couleurs de la carte
        """
        card = self.find_card_by_name(name)
        return set(card.get("colors", []))

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
    def load_from_csv(self, csv_path: str, import_type: str, progress_cb=None, label_cb=None) -> bool:
        """Charge la collection depuis un fichier CSV (compatibilité).
        
        Args:
            csv_path: Chemin vers le fichier CSV de collection.
            
        Returns:
            bool: True si le chargement a réussi, False sinon.
        """
        # try:
        cts.CSV_PATH = csv_path
        self.csv_path = Path(csv_path)
        self._load_csv_into_db(import_type, progress_cb, label_cb)
        return True
        # except Exception as e:
        #     logger.error(f"Erreur lors du chargement du CSV : {str(e)}")
        #     return False

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
                    "missing": max(0, quantity_needed - owned_quantity)

                })

        return results
