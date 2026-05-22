from typing import Any, Dict, Optional


class DeckAnalysisService:
    def __init__(self, collection_manager, external_provider, bulk_provider=None):
        self.collection_manager = collection_manager
        self.external_provider = external_provider
        self.bulk_provider = bulk_provider

    def summarize_deck(self, cards: list[dict]) -> dict:
        buckets = {k: 0 for k in ["0", "1", "2", "3", "4", "5", "6", "7+"]}
        total_cmc = 0.0
        cmc_count = 0
        lands = 0
        roles: dict[str, int] = {}
        colors = {k: 0 for k in ["W", "U", "B", "R", "G", "C"]}
        rarities: dict[str, int] = {}

        for card in cards:
            types = card.get("types", "")
            role = normalize_role_label(card.get("role") or "Other")
            roles[role] = roles.get(role, 0) + 1

            rarity = normalize_rarity_label(card.get("rarity") or "")
            rarities[rarity] = rarities.get(rarity, 0) + 1

            card_colors = self.collection_manager.get_card_colors(card.get("name", ""))
            if card_colors:
                for color in card_colors:
                    if color in colors:
                        colors[color] += 1
            elif "Land" not in types:
                colors["C"] += 1

            if "Land" in types:
                lands += 1
                continue

            cmc = self._get_card_cmc(card)
            if cmc is None:
                continue
            cmc_count += 1
            total_cmc += cmc
            if cmc >= 7:
                buckets["7+"] += 1
            else:
                bucket_key = str(int(cmc)) if cmc >= 0 else "0"
                if bucket_key not in buckets:
                    bucket_key = "7+"
                buckets[bucket_key] += 1

        return {
            "buckets": buckets,
            "total_cmc": total_cmc,
            "cmc_count": cmc_count,
            "lands": lands,
            "roles": roles,
            "colors": colors,
            "rarities": rarities,
            "total_cards": len(cards),
        }

    def compute_deck_stats(self, summary: dict) -> tuple[str, str]:
        buckets = summary["buckets"]
        total_cmc = summary["total_cmc"]
        cmc_count = summary["cmc_count"]
        lands = summary["lands"]
        roles = summary["roles"]
        total_cards = summary.get("total_cards", 0)

        curve_parts = [f"{k}: {v}" for k, v in buckets.items()]
        mana_curve_text = "Courbe de mana : " + " | ".join(curve_parts)

        avg_cmc = (total_cmc / cmc_count) if cmc_count else 0.0
        colors = summary.get("colors", {})
        color_text = ", ".join(
            f"{key}: {colors.get(key, 0)}" for key in ["W", "U", "B", "R", "G", "C"] if colors.get(key, 0)
        ) or "n/a"
        stats_lines = [
            f"Cartes totales : {total_cards}",
            f"Lands : {lands}",
            f"CMJ moyenne : {avg_cmc:.2f}" if cmc_count else "CMJ moyenne : n/a",
            "Répartition par rôle : " + ", ".join(f"{r}: {n}" for r, n in sorted(roles.items())),
            "Répartition couleurs : " + color_text,
        ]
        stats_text = "\n".join(stats_lines)
        return mana_curve_text, stats_text

    def _get_card_cmc(self, card: Dict[str, Any]) -> Optional[float]:
        scryfall_id = card.get("scryfall_id")
        cmc = None
        if scryfall_id and not str(scryfall_id).startswith("cardnexus::"):
            cmc = self.external_provider.get_card_cmc(scryfall_id)
        if cmc is None:
            card_name = card.get("name", "")
            bulk_data = self.bulk_provider.get_card_for_import(card_name=card_name) if (card_name and self.bulk_provider) else None
            if bulk_data:
                raw_cmc = bulk_data.get("cmc")
                try:
                    cmc = float(raw_cmc) if raw_cmc is not None else None
                except (TypeError, ValueError):
                    cmc = None
        return cmc


def normalize_role_label(role: str) -> str:
    value = str(role or "").strip()
    if not value:
        return "Other"

    normalized = value.lower().replace(" ", "").replace("-", "")
    aliases = {
        "ramp": "Ramp",
        "draw": "Draw",
        "carddraw": "Draw",
        "removal": "Removal",
        "interaction": "Removal",
        "finisher": "Finisher",
        "wincon": "Finisher",
        "wincondition": "Finisher",
        "land": "Land",
        "other": "Other",
    }
    return aliases.get(normalized, value.title())


def normalize_rarity_label(rarity: str) -> str:
    value = str(rarity or "").strip().lower()
    if not value:
        return "Unknown"

    aliases = {
        "common": "Common",
        "uncommon": "Uncommon",
        "rare": "Rare",
        "mythic": "Mythic",
        "mythic rare": "Mythic",
        "special": "Special",
    }
    return aliases.get(value, value.capitalize())
