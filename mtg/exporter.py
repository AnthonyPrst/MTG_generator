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
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
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
