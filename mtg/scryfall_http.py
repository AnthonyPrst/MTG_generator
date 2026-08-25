"""En-têtes HTTP partagés pour les appels à l'API Scryfall.

Scryfall rejette désormais les requêtes utilisant le User-Agent par défaut
de `requests` (erreur 400 `generic_user_agent`). Toutes les requêtes vers
`api.scryfall.com` doivent donc fournir un User-Agent personnalisé ainsi
qu'un header Accept explicite, comme recommandé par la documentation
Scryfall.
"""

SCRYFALL_HEADERS = {
    "User-Agent": "MTG-Generator/1.0 (+https://github.com/AnthonyPrst/MTG_generator)",
    "Accept": "application/json;q=0.9,*/*;q=0.8",
}
