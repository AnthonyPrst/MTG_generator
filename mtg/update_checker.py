"""Vérification des mises à jour disponibles via les GitHub Releases."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

GITHUB_API_RELEASES_LATEST = "https://api.github.com/repos/{repo}/releases/latest"
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "MTG-Generator-UpdateChecker",
}


def _parse_version(version: str) -> tuple:
    """Convertit une chaîne de version (ex: 'v1.8.0') en tuple comparable."""
    cleaned = version.strip().lower().lstrip("v")
    parts = []
    for part in cleaned.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_newer_version(remote_version: str, local_version: str) -> bool:
    """Indique si ``remote_version`` est strictement supérieure à ``local_version``."""
    return _parse_version(remote_version) > _parse_version(local_version)


@dataclass
class UpdateInfo:
    """Informations sur une mise à jour disponible."""
    version: str
    download_url: str
    release_notes: str
    html_url: str


class UpdateChecker:
    """Interroge l'API GitHub Releases pour détecter une nouvelle version.

    Args:
        repo: Dépôt GitHub au format ``owner/nom`` (ex: ``AnthonyPrst/MTG_generator``).
        asset_keyword: Sous-chaîne (insensible à la casse) recherchée dans le
            nom des assets pour identifier l'installateur à proposer.
    """

    def __init__(self, repo: str, asset_keyword: str = "installer"):
        self.repo = repo
        self.asset_keyword = asset_keyword.lower()

    def check_for_update(self, current_version: str) -> Optional[UpdateInfo]:
        """Retourne les informations de mise à jour si une version plus récente existe."""
        url = GITHUB_API_RELEASES_LATEST.format(repo=self.repo)
        try:
            response = requests.get(url, headers=GITHUB_HEADERS, timeout=10)
            response.raise_for_status()
            data: Dict[str, Any] = response.json()
        except Exception as e:
            logger.warning(f"Impossible de vérifier les mises à jour GitHub : {e}")
            return None

        tag_name = str(data.get("tag_name") or "").strip()
        if not tag_name or not is_newer_version(tag_name, current_version):
            return None

        assets: List[Dict[str, Any]] = data.get("assets") or []
        download_url = None
        for asset in assets:
            name = str(asset.get("name") or "").lower()
            if self.asset_keyword in name and name.endswith(".exe"):
                download_url = asset.get("browser_download_url")
                break
        if not download_url:
            for asset in assets:
                name = str(asset.get("name") or "").lower()
                if name.endswith(".exe"):
                    download_url = asset.get("browser_download_url")
                    break

        if not download_url:
            logger.warning(
                f"Nouvelle version {tag_name} détectée mais aucun installateur (.exe) trouvé dans les assets."
            )
            return None

        return UpdateInfo(
            version=tag_name,
            download_url=download_url,
            release_notes=str(data.get("body") or ""),
            html_url=str(data.get("html_url") or ""),
        )
