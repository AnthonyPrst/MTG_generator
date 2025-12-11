"""Validation des decks Commander."""

from typing import Dict, List, Tuple

class DeckValidator:
    """Valide la conformité d'un deck Commander."""
    
    def validate_deck(self, deck: Dict) -> Tuple[bool, List[str]]:
        """Valide un deck Commander.
        
        Args:
            deck: Structure du deck à valider.
            
        Returns:
            Tuple[bool, List[str]]: (valide, liste_des_erreurs)
        """
        pass

    def _check_singleton(self, deck: Dict) -> List[str]:
        """Vérifie la règle du singleton.
        
        Args:
            deck: Structure du deck.
            
        Returns:
            List[str]: Liste des erreurs de singleton.
        """
        pass

    def _check_color_identity(self, deck: Dict) -> List[str]:
        """Vérifie l'identité de couleur.
        
        Args:
            deck: Structure du deck.
            
        Returns:
            List[str]: Liste des erreurs d'identité de couleur.
        """
        pass

    def _check_deck_size(self, deck: Dict) -> List[str]:
        """Vérifie la taille du deck.
        
        Args:
            deck: Structure du deck.
            
        Returns:
            List[str]: Liste des erreurs de taille.
        """
        pass
