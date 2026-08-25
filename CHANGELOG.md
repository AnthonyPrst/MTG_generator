# Changelog

All notable changes to this project are documented in this file.

The format is inspired by `Keep a Changelog`, and versioning follows `SemVer` where practical.

## [v1.8.0] - 2026-08-25

### Added

- Automatic and manual update checker based on GitHub Releases, with a "Vérifier les mises à jour" button in the Settings tab.
- Update dialog now renders the GitHub release notes (Markdown) and lets the user download and launch the installer directly from the app.
- The main window now adapts its size and position to the user's screen resolution instead of using a fixed size.

### Changed

- The sidebar and stats panel now keep a fixed, screen-proportional width so heavy center content (deck table, image gallery) can no longer shrink them after a deck is generated.
- The deck image gallery column count now adapts to the available width instead of always using 4 fixed columns.
- All Scryfall API requests now send a custom `User-Agent` and `Accept` header (`mtg.scryfall_http.SCRYFALL_HEADERS`), as Scryfall now rejects the default `requests` user agent.

### Fixed

- Fixed intermittent Scryfall API request failures (`400 generic_user_agent`) across sync, card image preview, EDHREC analytics, and external data lookups.

## [v1.7.0] - 2026-05-18

### Added

- Commander color identity filtering for candidate cards directly when building the eventual card list.
- Pauper mode in the deck-building interface.
- More reliable commander candidate detection and availability handling using local Scryfall bulk data.

### Changed

- Collection import is now limited to the `CardNexus` and `ManaBox` formats.
- Commander preview now uses local Scryfall data more effectively, with remote fallback when needed.
- Commander selection in the UI now ignores partial or unknown names before triggering related updates.
- Candidate card generation is now aligned with the color identity rules already enforced by the deck builder.

### Fixed

- Deck building is now guarded when no eventual card list has been loaded yet.
- Fixed a case where cards outside the commander's color identity could appear in the eventual card list.
- Improved detection of eligible commanders, including some legendary artifact `Vehicle` and `Spacecraft` cards.

## [v1.6.0] - 2026-05-18

### Added

- Local Scryfall synchronization to reduce dependency on live API calls.
- Extended PySide6 interface with build, collection, and settings tabs.
- Card and commander preview support in the UI.
- Deck-building strategy management with key role targets such as `ramp`, `draw`, `removal`, `boardwipe`, and `win condition`.
- CSV collection import with support for multiple historical formats.
- Deck export to `TXT`, `CSV`, and `Archidekt`.
- Comparison between source decks and the local collection to produce a candidate card list.

### Changed

- Improved the overall Commander deck generation workflow using local collection data and external sources.
- Centralized application version display in the main window and settings tab.

## [v1.0.0] - Initial release

### Added

- Initial functional foundation of the Commander deck generator.
- Local collection management backed by SQLite.
- Automatic deck building from a user's collection.

## Notes

- Older changes were not previously consolidated into a dedicated changelog.
- This file becomes the reference source for release history starting with `v1.7.0`.
