from gui.tabs.build_tab import (
    _normalize_role_label,
    _selection_stage_badge_label,
    _selection_stage_color,
    _selection_stage_label,
)
from gui.widgets.stats_panel import _format_goals_summary


def test_selection_stage_label_covers_known_selection_paths():
    assert _selection_stage_label("") == "Ajoutée au deck"
    assert _selection_stage_label("commander_seed") == "Ajoutée comme commandant du deck"
    assert _selection_stage_label("commander_fallback") == "Ajoutée comme commandant via récupération externe"
    assert _selection_stage_label("role:Ramp") == "Sélectionnée pour atteindre le quota de rôle : Ramp"
    assert _selection_stage_label("fill:nonland") == "Ajoutée pour compléter les cartes non-terrain"
    assert _selection_stage_label("fill:collection_limit") == "Ajoutée pour compléter le deck malgré une collection limitée"
    assert _selection_stage_label("land:distinct") == "Ajoutée comme terrain distinct"
    assert _selection_stage_label("land:basic_fill") == "Ajoutée comme terrain de base pour atteindre le quota de terrains"


def test_selection_stage_label_falls_back_for_unknown_stage():
    assert _selection_stage_label("mystery:stage") == "Étape de sélection : mystery:stage"


def test_normalize_role_label_covers_boardwipe_variations():
    assert _normalize_role_label("removal") == "Removal"
    assert _normalize_role_label("Removal") == "Removal"
    assert _normalize_role_label("interaction") == "Removal"


def test_selection_stage_badge_and_color_cover_known_paths():
    assert _selection_stage_badge_label("commander_seed") == "Commandant"
    assert _selection_stage_badge_label("role:Ramp") == "Quota Ramp"
    assert _selection_stage_badge_label("land:basic_fill") == "Base land"
    assert _selection_stage_color("commander_seed") == "#d29922"
    assert _selection_stage_color("role:Ramp") == "#58a6ff"
    assert _selection_stage_color("land:basic_fill") == "#3fb950"


def test_format_goals_summary_reports_current_vs_targets():
    summary = {
        "lands": 36,
        "roles": {
            "Ramp": 11,
            "Draw": 9,
            "Removal": 8,
            "Finisher": 6,
        },
        "targets": {
            "lands_min": 35,
            "lands_max": 38,
            "roles": {
                "Ramp": 12,
                "Draw": 10,
                "Removal": 8,
                "Finisher": 6,
            },
        },
    }

    text = _format_goals_summary(summary)

    assert "Terrains : 36 / cible 35-38  ·  OK" in text
    assert "Ramp : 11 / 12  ·  Proche" in text
    assert "Removal : 8 / 8  ·  OK" in text
