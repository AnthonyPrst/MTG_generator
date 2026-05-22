"""Définition des formats d'import pour différentes plateformes MTG."""

from abc import ABC, abstractmethod
from typing import Dict, List, Set, Optional, Any
import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ImportFormat(ABC):
    """Classe de base pour les formats d'import."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nom du format d'import."""
        pass
    
    @property
    @abstractmethod
    def required_columns(self) -> Set[str]:
        """Colonnes requises dans le fichier CSV."""
        pass
    
    @property
    @abstractmethod
    def optional_columns(self) -> Set[str]:
        """Colonnes optionnelles dans le fichier CSV."""
        pass
    
    @abstractmethod
    def process_row(self, row: Dict[str, str], external_provider, bulk_provider=None) -> Dict[str, Any]:
        """Transforme une ligne du CSV en données pour la base de données.
        
        Args:
            row: Ligne du fichier CSV
            external_provider: Provider pour les données externes (Scryfall)
            bulk_provider: ScryfallSyncManager optionnel pour lookup local
            
        Returns:
            Dictionnaire avec les données de la carte pour la DB
        """
        pass
    
    def validate_columns(self, fieldnames: Optional[List[str]]) -> None:
        """Valide que les colonnes requises sont présentes."""
        if fieldnames is None:
            fieldnames = []
        
        fieldnames_set = set(fieldnames)
        missing_columns = self.required_columns - fieldnames_set
        
        if missing_columns:
            raise ValueError(f"Le fichier {self.name} doit contenir les colonnes : {missing_columns}")
    
    def get_column_value(self, row: Dict[str, str], column: str, default: str = "") -> str:
        """Récupère la valeur d'une colonne avec une valeur par défaut."""
        return row.get(column, default).strip()


class ManaBoxFormat(ImportFormat):
    """Format d'import pour ManaBox."""
    
    @property
    def name(self) -> str:
        return "ManaBox - Collection"
    
    @property
    def required_columns(self) -> Set[str]:
        return {
            'Name', 'Set code', 'Set name', 'Collector number', 
            'Foil', 'Rarity', 'Quantity', 'Scryfall ID', 'Condition', 'Language'
        }
    
    @property
    def optional_columns(self) -> Set[str]:
        return set()
    
    def _extract_card_info(self, card_data: Dict) -> tuple:
        """Extrait oracle_id, image, types, colors depuis un dict Scryfall."""
        oracle_id = card_data.get('oracle_id', '')
        types = card_data.get('type_line', '')
        colors = card_data.get('color_identity', [])
        image = ''
        
        if 'image_uris' in card_data:
            urls = card_data['image_uris']
            image = urls.get('normal') or urls.get('large') or urls.get('png', '')
        
        faces = card_data.get('card_faces')
        if faces and not image:
            for face in faces:
                urls = face.get('image_uris')
                if urls:
                    image = urls.get('normal') or urls.get('large') or urls.get('png', '')
                    break
        
        return oracle_id, image, types, colors
    
    def process_row(self, row: Dict[str, str], external_provider, bulk_provider=None) -> Dict[str, Any]:
        card_name = self.get_column_value(row, 'Name')
        scryfall_id = self.get_column_value(row, 'Scryfall ID')
        
        oracle_id, image, types, colors = '', '', '', []
        
        # 1. Essayer le bulk data local (instantané, pas d'API)
        if bulk_provider:
            card_data = bulk_provider.get_card_for_import(
                scryfall_id=scryfall_id, card_name=card_name
            )
            if card_data:
                oracle_id, image, types, colors = self._extract_card_info(card_data)
        
        # 2. Fallback API Scryfall seulement si bulk n'a pas trouvé
        if not types and external_provider:
            try:
                card_data = external_provider.get_scryfall_data(scryfall_id)
                oracle_id, image, types, colors = self._extract_card_info(card_data)
            except Exception as e:
                logger.warning(f"Impossible de récupérer les données Scryfall pour {card_name}: {e}")
        
        return {
            'name': card_name,
            'colors': str(colors),
            'types': types,
            'scryfall_id': scryfall_id,
            'oracle_id': oracle_id,
            'set_code': self.get_column_value(row, 'Set code'),
            'set_name': self.get_column_value(row, 'Set name'),
            'collector_number': self.get_column_value(row, 'Collector number'),
            'image_url': image,
            'foil': 1 if self.get_column_value(row, 'Foil').lower() == 'foil' else 0,
            'rarity': self.get_column_value(row, 'Rarity'),
            'quantity': int(self.get_column_value(row, 'Quantity', '1')),
            'card_condition': self.get_column_value(row, 'Condition'),
            'language': self.get_column_value(row, 'Language', 'English')
        }


class CardNexusFormat(ImportFormat):
    """Format d'import pour CardNexus."""

    @property
    def name(self) -> str:
        return "CardNexus"

    @property
    def required_columns(self) -> Set[str]:
        return {'totalQtyOwned', 'name', 'expansion', 'printNumber', 'language', 'condition'}

    @property
    def optional_columns(self) -> Set[str]:
        return {'finish', 'rarity', 'price', 'color', 'colorIdentity', 'types', 'variant'}

    @staticmethod
    def _extract_from_card_data(card_data: Dict) -> tuple:
        """Extrait les infos utiles d'un dict Scryfall."""
        oracle_id = card_data.get('oracle_id', '')
        scryfall_id = card_data.get('id', '')
        types = card_data.get('type_line', '')
        colors = card_data.get('color_identity', [])
        set_code = card_data.get('set', '').upper()
        collector_number = card_data.get('collector_number', '')
        image = ''

        if 'image_uris' in card_data:
            urls = card_data['image_uris']
            image = urls.get('normal') or urls.get('large') or urls.get('png', '')

        faces = card_data.get('card_faces')
        if faces and not image:
            for face in faces:
                urls = face.get('image_uris')
                if urls:
                    image = urls.get('normal') or urls.get('large') or urls.get('png', '')
                    break

        return oracle_id, scryfall_id, types, colors, set_code, collector_number, image

    @staticmethod
    def _looks_like_set_code(value: str) -> bool:
        token = str(value or "").strip()
        return bool(token) and len(token) <= 6 and token.replace("-", "").isalnum()

    def process_row(self, row: Dict[str, str], external_provider, bulk_provider=None) -> Dict[str, Any]:
        card_name = self.get_column_value(row, 'name')
        set_name = self.get_column_value(row, 'expansion')
        set_code_input = set_name if self._looks_like_set_code(set_name) else ""
        resolved_set_code = ""
        if external_provider:
            resolved_set_code = external_provider.resolve_set_code(set_code=set_code_input, set_name=set_name)
        elif set_code_input:
            resolved_set_code = set_code_input.lower()
        collector_number = self.get_column_value(row, 'printNumber')

        oracle_id, image, types, colors, scryfall_id, set_code_from_api, collector_number_from_api = "", "", "", [], "", "", ""
        matched_exact_print = False

        # 1. Essayer le bulk data local (rapide)
        if bulk_provider:
            card_data = bulk_provider.get_card_for_import(card_name=card_name)
            if card_data:
                oracle_id, scryfall_id, types, colors, set_code_from_api, collector_number_from_api, image = self._extract_from_card_data(card_data)

                if collector_number:
                    matched_exact_print = (
                        bool(set_code_from_api)
                        and bool(collector_number_from_api)
                        and bool(resolved_set_code)
                        and set_code_from_api.lower() == resolved_set_code.lower()
                        and collector_number_from_api.strip().lower() == collector_number.strip().lower()
                    )

        # 2. API exact print seulement si nécessaire
        if not matched_exact_print and external_provider and collector_number and resolved_set_code:
            exact_card_data = external_provider.get_card_for_exact_print(
                set_code=resolved_set_code,
                collector_number=collector_number,
                set_name=set_name,
            )
            if exact_card_data:
                oracle_id, scryfall_id, types, colors, set_code_from_api, collector_number_from_api, image = self._extract_from_card_data(exact_card_data)
                matched_exact_print = bool(scryfall_id)

        # 3. Fallback API seulement si aucun résultat exploitable
        if not matched_exact_print and not types and external_provider:
            try:
                card_data = external_provider.get_scryfall_data(card_name)
                oracle_id, scryfall_id, types, colors, set_code_from_api, collector_number_from_api, image = self._extract_from_card_data(card_data)
            except Exception as e:
                logger.warning(f"Impossible de trouver les données pour {card_name}: {e}")

        if not colors and types and 'Land' not in types:
            colors = ['colorless']

        matched_exact_print = matched_exact_print or (
            bool(scryfall_id)
            and bool(set_code_from_api)
            and bool(collector_number_from_api)
            and set_code_from_api.lower() == resolved_set_code.lower()
            and collector_number_from_api.strip().lower() == collector_number.strip().lower()
        )

        if not matched_exact_print:
            fallback_key_parts = [
                "cardnexus",
                card_name.lower(),
                set_name.lower(),
                collector_number.lower(),
                self.get_column_value(row, 'finish').lower(),
                self.get_column_value(row, 'language', 'english').lower(),
            ]
            scryfall_id = "::".join(fallback_key_parts)

        effective_set_code = set_code_from_api if matched_exact_print else resolved_set_code
        effective_collector_number = collector_number_from_api if matched_exact_print else collector_number

        return {
            'name': card_name,
            'colors': str(colors),
            'types': types,
            'scryfall_id': scryfall_id,
            'oracle_id': oracle_id,
            'set_code': effective_set_code,
            'set_name': set_name,
            'collector_number': effective_collector_number,
            'image_url': image,
            'foil': 1 if self.get_column_value(row, 'finish').lower() == 'foil' else 0,
            'rarity': self.get_column_value(row, 'rarity'),
            'quantity': int(self.get_column_value(row, 'totalQtyOwned', '1')),
            'card_condition': self.get_column_value(row, 'condition'),
            'language': self.get_column_value(row, 'language', 'English')
        }


class MTGArenaFormat(ImportFormat):
    """Format d'import pour MTG Arena."""

    @property
    def name(self) -> str:
        return "MTG Arena"

    @property
    def required_columns(self) -> Set[str]:
        return {'Card Name', 'Set Name', 'Set Code', 'Card Number', 'Quantity'}

    @property
    def optional_columns(self) -> Set[str]:
        return set()

    @staticmethod
    def _extract_from_card_data(card_data: Dict) -> tuple:
        """Extrait les infos utiles d'un dict Scryfall."""
        oracle_id = card_data.get('oracle_id', '')
        scryfall_id = card_data.get('id', '')
        types = card_data.get('type_line', '')
        colors = card_data.get('color_identity', [])
        set_code = card_data.get('set', '').upper()
        collector_number = card_data.get('collector_number', '')
        image = ''

        if 'image_uris' in card_data:
            urls = card_data['image_uris']
            image = urls.get('normal') or urls.get('large') or urls.get('png', '')

        faces = card_data.get('card_faces')
        if faces and not image:
            for face in faces:
                urls = face.get('image_uris')
                if urls:
                    image = urls.get('normal') or urls.get('large') or urls.get('png', '')
                    break

        return oracle_id, scryfall_id, types, colors, set_code, collector_number, image

    def process_row(self, row: Dict[str, str], external_provider, bulk_provider=None) -> Dict[str, Any]:
        card_name = self.get_column_value(row, 'Card Name')

        # Skip les cartes avec des noms invalides (commençant par "Card_")
        if card_name.startswith('Card_'):
            logger.warning(f"Carte ignorée : nom invalide '{card_name}'")
            raise ValueError(f"Nom de carte invalide : {card_name}")

        set_name = self.get_column_value(row, 'Set Name')
        set_code = self.get_column_value(row, 'Set Code')
        collector_number = self.get_column_value(row, 'Card Number')
        quantity = int(self.get_column_value(row, 'Quantity', '1'))

        # Résoudre le nom du set si c'est "Unknown" mais qu'on a un code de set valide
        if set_name.lower() == 'unknown' and set_code and external_provider:
            try:
                resolved_set_name = external_provider.resolve_set_name(set_code=set_code)
                if resolved_set_name and resolved_set_name.lower() != 'unknown':
                    set_name = resolved_set_name
            except Exception:
                pass

        oracle_id, image, types, colors, scryfall_id = "", "", "", [], ""

        # 1. Essayer le bulk data local (rapide)
        if bulk_provider:
            card_data = bulk_provider.get_card_for_import(card_name=card_name)
            if card_data:
                oracle_id, scryfall_id, types, colors, set_code_from_api, collector_number_from_api, image = self._extract_from_card_data(card_data)

                # Valider que le set code et collector number correspondent
                if set_code_from_api and collector_number_from_api:
                    if set_code_from_api.lower() == set_code.lower() and collector_number_from_api.strip().lower() == collector_number.strip().lower():
                        # Match exact, utiliser les données du bulk
                        pass
                    else:
                        # Même nom mais pas la même impression, garder les données du CSV
                        scryfall_id = ""

        # 2. Fallback API seulement si bulk n'a pas trouvé ou n'a pas matché exactement
        if not types and external_provider:
            try:
                card_data = external_provider.get_scryfall_data(card_name)
                oracle_id, scryfall_id, types, colors, set_code_from_api, collector_number_from_api, image = self._extract_from_card_data(card_data)
            except Exception as e:
                logger.warning(f"Impossible de trouver les données pour {card_name}: {e}")

        if not colors and types and 'Land' not in types:
            colors = ['colorless']

        # Fallback ID si pas de scryfall_id
        if not scryfall_id:
            fallback_key_parts = [
                "mtga",
                card_name.lower(),
                set_code.lower(),
                collector_number.lower(),
            ]
            scryfall_id = "::".join(fallback_key_parts)

        return {
            'name': card_name,
            'colors': str(colors),
            'types': types,
            'scryfall_id': scryfall_id,
            'oracle_id': oracle_id,
            'set_code': set_code,
            'set_name': set_name,
            'collector_number': collector_number,
            'image_url': image,
            'foil': 0,  # MTG Arena n'a pas de foil dans ce format
            'rarity': '',
            'quantity': quantity,
            'card_condition': '',
            'language': 'English'  # MTG Arena est principalement en anglais
        }


# Registre des formats d'import
IMPORT_FORMATS = {
    "ManaBox - Collection": ManaBoxFormat(),
    "CardNexus": CardNexusFormat(),
    "MTG Arena": MTGArenaFormat(),
}


def get_import_format(format_name: str) -> Optional[ImportFormat]:
    """Récupère un format d'import par son nom."""
    return IMPORT_FORMATS.get(format_name)


def detect_format(file_path: str) -> Optional[ImportFormat]:
    """Détecte automatiquement le format d'un fichier CSV."""
    try:
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            fieldnames = set(reader.fieldnames or [])
            
            # Tester chaque format
            for format_name, format_class in IMPORT_FORMATS.items():
                if format_class.required_columns.issubset(fieldnames):
                    logger.info(f"Format détecté automatiquement : {format_name}")
                    return format_class
                    
    except Exception as e:
        logger.error(f"Erreur lors de la détection du format : {e}")
    
    return None


def get_available_formats() -> List[str]:
    """Retourne la liste des formats d'import disponibles."""
    return list(IMPORT_FORMATS.keys())
