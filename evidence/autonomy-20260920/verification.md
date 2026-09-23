# Prüfnotizen

- 77 Softwaretests bestanden in 19,42 Sekunden.
- 48 Live-Läufe vollständig erhalten; in allen Jev-only-Läufen null GPT-Aufrufe.
- In beiden Varianten null neue Werkzeugbauten; maximal zwei GPT-Aufrufe erlaubt,
  tatsächlich genau ein Vorbereitungsaufruf pro unterstütztem Lauf.
- Kein GPT-Webzugriff oder MCP-Werkzeugaufruf in den Protokollen.
- Nach dem Start der Läufe wurde ein allgemeiner Reihenfolgefehler im Auswerter
  korrigiert: Eine ältere GPT-Prüfung darf eine spätere Jev-Entscheidung nicht verdecken.
  Die korrigierte Auswertung wurde mechanisch auf sämtliche 48 Original-Läufe angewandt;
  alle Bewertungen blieben identisch. Es gab hier keine GPT-Entscheidungsprüfungen.
  Ein Regressionstest deckt diesen Fall ab. Die tatsächlich ausgeführten Quelldateien
  sind in executed-source archiviert und entsprechen den Hashes im eingefrorenen Protokoll.
- Originalwerte, fehlgeschlagene Läufe und Grenzfälle wurden weder entfernt noch wiederholt.
