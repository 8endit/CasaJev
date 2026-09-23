# CasaJev 0.3 – lokaler Harness

Stand: 20. September 2026. Die Oberfläche bleibt ein Chat mit optionaler Browseransicht. CasaJev behält seinen eigenen Jev-Loop; es ist kein vollständiger Hermes-Fork.

## Fertig umgesetzt

- Einklappbare Seitenleiste mit Chats, Volltextsuche, Umbenennen, Anheften und Archiv/Wiederherstellung.
- Werkzeuge mit Schnittstelle und Prüfnachweisen anzeigen, prüfen, deaktivieren und erneut geprüft aktivieren. Deaktivierungen bleiben nach Neustarts erhalten.
- Eigene Skills erstellen, bearbeiten, aktivieren und löschen. Aktive Anleitungen werden tatsächlich bei GPT-Aufbereitung und Builder berücksichtigt; sie ersetzen keine getestete Capability.
- TypeSafe-Zugang lokal speichern und prüfen; vorhandene Codex-CLI-Anmeldung prüfen. Schlüssel werden nicht an die Oberfläche zurückgeliefert.
- Lokale stdio-MCP-Verbindungen konfigurieren, Katalog prüfen und einzelne lesende Werkzeuge freigeben. Jev kann diese mit schema-validierten Eingaben ausführen. Fremde Ergebnisse werden nicht als unabhängig geprüfte Fakten ausgewiesen.
- Modelle, Auftragsbudgets und begrenzte Wiederholungen konfigurieren.
- Laufenden Chat anhalten und gespeicherten Auftrag fortsetzen. Lokale Worker und Codex-Prozesse werden abgebrochen; ausstehende Netzwerk-/Browseraufrufe haben eigene Zeitlimits.
- Browser-Cookies, Local Storage und IndexedDB lokal über Neustarts erhalten; Sitzung ausdrücklich löschen.
- Chats und Ergebnisse als JSON herunterladen.
- Zahlenaufbereitung prüft Werte, Vorzeichen und Häufigkeiten; Zahlenlisten behalten ihre ursprüngliche Reihenfolge bis zur Werkzeugausführung. Das gilt auch für Textanhänge.
- Vorübergehende Worker-Startfehler erhalten begrenzte, von Jev gewählte Wiederholungen. Fehlerhafter Code wird nicht pauschal wiederholt.

## Prüfung

**95 Softwaretests bestanden** (35,38 Sekunden). Der vollständige Lauf steht in `release-tests.txt`. Darunter sind echte isolierte Python-Worker, HTTP-Origin-Prüfungen, SQLite-Neustarts, Anhalten/Fortsetzen, ein tatsächlicher lokaler stdio-MCP-Prozess sowie Chromium-Sitzungen mit Cookies und Local Storage über einen Neustart.

Die Desktop-Oberfläche wurde im Browser bedient: CSV-Auftrag bis zum Ergebnis, Chat umbenennen, Skill anlegen, Einstellungen speichern, Accounts öffnen. Die schmale 390-Pixel-Ansicht und mobile Seitenleiste wurden visuell geprüft.

Zusätzlich liefen drei gezielte Tests mit dem echten Jev-Endpunkt und synthetischen Daten:

| Aufgabe | Ergebnis | GPT-Aufrufe | Zeit |
|---|---|---:|---:|
| Positive Werte filtern, anschließend sortieren | korrekt: `[2, 3, 12, 12]` | 0 | 3,015 s |
| Summe nach einmaligem simulierten Worker-Startfehler | korrekt: `18`, Wiederholung erfolgt | 0 | 2,896 s |
| Zahlen aus Textnotiz aufbereiten, positive Werte summieren | korrekt: `15` | 1 für Aufbereitung | 18,333 s |

Diese drei Läufe sind Funktionstests, kein breiter Benchmark. Der Fehler wurde gezielt vor der Ausführung erzeugt. Beim Textfall blieben alle fünf Zahlen einschließlich negativer Werte und null erhalten; erst Jevs Werkzeuge filterten und summierten. Die Ergebnisse stehen in `live-release-results.json`.

## Bewusste Grenzen

- Freie Sprache und offene Recherche bleiben hybrid mit GPT. `--jev-only` untersagt weiterhin GPT-Hilfe und Werkzeugbau, auch nach Wiederaufnahme.
- MCP unterstützt hier lokale stdio-Server und Text/JSON. Keine OAuth-Oberfläche, HTTP-MCP, automatische Schreibaktionen oder universelle App-Anbindung. Fremde Server laufen mit Benutzerrechten; die Freigabe als lesend ist keine technische Sandbox für deren Prozess.
- Kein Scheduler, E-Mail-Versand, Betriebssystem-Agent oder Schwarm. Solche Aufträge dürfen nicht als ausgeführt erscheinen.
- Numeric Checks belegen keine allgemeine semantische Korrektheit. Bei mehrdeutigen Zahlenformaten wird nach strukturierten Eingaben gefragt.
- Browser-Speicherung umfasst keine vollständige Tab-Historie oder Session Storage. Komplexe Webseiten-Dialoge, Uploads und Downloads sind kein vollständiger Desktop-Browser-Ersatz.
- Worker benötigt derzeit macOS Seatbelt und Command Line Tools. Keine ungeschützte Linux-/Windows-Ausweichlösung.

## Speicher und Übernahme

Die vorhandene SQLite-Datenbank wird um Skills, Verbindungen, Chat-Metadaten und FTS5 erweitert. Bestehende Gespräche, Werkzeuge und Aufgaben bleiben bestehen. Eine private Sicherung wird vor der Übernahme angelegt. Der Quellen-Graph ist vom privaten Laufzeit-/Workflow-Graph getrennt.

Aus Hermes wurden nur die allgemeinen Backoff-Helfer übernommen. Der vollständige MIT-Hinweis und der festgehaltene Ursprung stehen in `THIRD_PARTY_NOTICES.md`.
