"""Exportation des decks générés."""

import csv
import json
from pathlib import Path
from typing import Dict, List, Union, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DeckExporter:
    """Gère l'exportation des decks dans différents formats."""
    
    def __init__(self, output_dir: str = "decks"):
        """Initialise l'exporteur avec un répertoire de sortie.
        
        Args:
            output_dir: Répertoire de base pour les exports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
    
    def export_to_txt(self, deck: Dict, filename: Optional[str] = None) -> Path:
        """Exporte le deck au format texte.
        
        Format:
            Commander
            1x Carte 1
            1x Carte 2
            ...
            
        Args:
            deck: Dictionnaire contenant les informations du deck
            filename: Nom du fichier de sortie (sans extension)
            
        Returns:
            Path: Chemin du fichier généré
        """
        if not filename:
            filename = f"deck_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output_path = self.output_dir / f"{filename}.txt"
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # Écriture du commandant
                f.write(f"Commander\n1x {deck['commander']['name']}\n\n")
                
                # Écriture des cartes du deck
                f.write("Deck\n")
                for card in deck['cards']:
                    f.write(f"{card.get('quantity', 1)}x {card['name']}\n")
                
            logger.info(f"Deck exporté avec succès au format TXT: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Erreur lors de l'export TXT: {str(e)}")
            raise
    
    def export_to_csv(self, deck: Dict, filename: Optional[str] = None) -> Path:
        """Exporte le deck au format CSV.
        
        Format:
            Name,Quantity,Type,Color Identity,CMC
            Sol Ring,1,Artifact,,1
            ...
            
        Args:
            deck: Dictionnaire contenant les informations du deck
            filename: Nom du fichier de sortie (sans extension)
            
        Returns:
            Path: Chemin du fichier généré
        """
        if not filename:
            filename = f"deck_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output_path = self.output_dir / f"{filename}.csv"
        
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['Name', 'Quantity', 'Type', 'Color Identity', 'CMC']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=";")
                
                writer.writeheader()
                
                # Écriture du commandant
                writer.writerow({
                    'Name': deck['commander']['name'],
                    'Quantity': 1,
                    'Type': deck['commander'].get('type', ''),
                    'Color Identity': ''.join(deck['commander'].get('color_identity', [])),
                    'CMC': deck['commander'].get('cmc', 0)
                })
                
                # Écriture des cartes du deck
                for card in deck['cards']:
                    writer.writerow({
                        'Name': card['name'],
                        'Quantity': card.get('quantity', 1),
                        'Type': card.get('type', ''),
                        'Color Identity': ''.join(card.get('color_identity', [])),
                        'CMC': card.get('cmc', 0)
                    })
                    
            logger.info(f"Deck exporté avec succès au format CSV: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Erreur lors de l'export CSV: {str(e)}")
            raise
    
    def export_to_archidekt(self, deck: Dict, filename: Optional[str] = None) -> Path:
        """Exporte le deck au format Archidekt (JSON).
        
        Args:
            deck: Dictionnaire contenant les informations du deck
            filename: Nom du fichier de sortie (sans extension)
            
        Returns:
            Path: Chemin du fichier généré
        """
        if not filename:
            filename = f"deck_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output_path = self.output_dir / f"{filename}.json"
        
        try:
            archidekt_format = {
                "name": f"Deck {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "format": "commander",
                "visibility": "private",
                "description": f"Généré automatiquement le {datetime.now().strftime('%Y-%m-%d')}",
                "playtest": False,
                "cards": []
            }
            
            # Ajout du commandant
            archidekt_format["cards"].append({
                "quantity": 1,
                "card": {
                    "scryfallId": deck['commander'].get('scryfall_id', ''),
                    "oracleId": deck['commander'].get('oracle_id', ''),
                    "name": deck['commander']['name'],
                    "isCommander": True
                }
            })
            
            # Ajout des cartes du deck
            for card in deck['cards']:
                archidekt_format["cards"].append({
                    "quantity": card.get('quantity', 1),
                    "card": {
                        "scryfallId": card.get('scryfall_id', ''),
                        "oracleId": card.get('oracle_id', ''),
                        "name": card['name']
                    }
                })
            
            # Écriture du fichier JSON
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(archidekt_format, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Deck exporté avec succès au format Archidekt: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Erreur lors de l'export Archidekt: {str(e)}")
            raise

    def export_deck_to_txt(self, scryfall_id_list: List[str], commander_name: str, conn, format: str = "standard", filename: Optional[str] = None, output_dir: Optional[Path] = None) -> Path:
        """Exporte une liste de cartes au format texte standard.

        Format:
            Commander
            1x Nom de carte (SET) numéro
            1x Nom de carte

        Args:
            scryfall_id_list: Liste d'identifiants Scryfall
            commander_name: Nom du commandant
            conn: Connexion SQLite à la base de données
            filename: Nom du fichier de sortie (sans extension)
            output_dir: Répertoire de sortie (par défaut self.output_dir)

        Returns:
            Path: Chemin du fichier généré
        """
        if not filename:
            filename = f"deck_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if output_dir is None:
            output_dir = self.output_dir
        output_path = output_dir / f"{filename}.txt"

        if not scryfall_id_list:
            logger.warning("Liste de scryfall_id vide, rien à exporter")
            return output_path

        # Compter les occurrences de chaque scryfall_id (quantité dans le deck)
        from collections import Counter
        scryfall_id_counts = Counter(scryfall_id_list)

        # Récupération des cartes depuis la base
        placeholders = ",".join(["?"] * len(scryfall_id_counts))
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM cards WHERE cards.scryfall_id IN ({placeholders}) ORDER BY cards.name",
            list(scryfall_id_counts.keys()),
        )
        cards = [dict(row) for row in cursor.fetchall()]

        if not cards:
            logger.warning("Aucune carte trouvée pour les scryfall_id fournis")
            return output_path

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                if format == "standard":
                    f.write(f"Commander\n1x {commander_name}\n\n")
                else:
                    f.write(f"Commander\n1 {commander_name}\n\n")
                f.write("Deck\n")
                for card in cards:
                    # Utiliser la quantité du deck (comptée depuis la liste) et non celle de la collection
                    scryfall_id = card.get("scryfall_id")
                    qty = scryfall_id_counts.get(scryfall_id, 1)
                    name = card.get("name", "?")
                    set_code = card.get("set_code", "")
                    collector = card.get("collector_number", "")

                    # Format type : "1x Nom de carte (SET) numéro"
                    if format == "standard":
                        if set_code and collector:
                            line = f"{qty}x {name} ({set_code}) {collector}\n"
                        else:
                            line = f"{qty}x {name}\n"
                    else:
                        line = f"{qty} {name}\n"
                    f.write(line)

            logger.info(f"Deck exporté avec succès au format standard TXT: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Erreur lors de l'export standard TXT: {str(e)}")
            raise
