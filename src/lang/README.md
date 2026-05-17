# Translations

Each `<locale>.json` file under this directory is a flat key → string map. The
key is the lookup name (referenced from Vue components via `$t("…")`); the
value is the translation.

## Adding a new language

1. Copy `en.json` to a new file using the locale code as the filename, e.g.
   `de-DE.json` for German (Germany).
2. Translate the values, leaving keys untouched.
3. Register the language in `../i18n.js` by adding an entry to
   `languageList`, format: `"de-DE": "Deutsch",`.
4. Open a PR with the new file + the `i18n.js` change.

## Updating an existing language

Edit the `<locale>.json` file directly. Keep keys identical to `en.json` — any
key present in `en.json` but missing from the locale falls back to English at
runtime.

If you do not have programming skills, open an issue and a maintainer will
assist with the wiring.
