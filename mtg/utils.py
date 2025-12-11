"""Utilitaires divers pour l'application."""

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Types personnalisés
Card = Dict[str, Any]
Deck = Dict[str, Any]

def setup_logging(log_level: str = "INFO") -> None:
    """Configure le système de logging.
    
    Args:
        log_level: Niveau de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
