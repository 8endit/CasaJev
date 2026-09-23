# CasaJev: Was schafft Jev ohne GPT?

Live-Prüfung vom 20.09.2026. Zwölf vorab festgelegte synthetische Fälle, zwei Wiederholungen, zwei Varianten: **48 Läufe**. Aufgaben und Kriterien wurden vor dem ersten Modellaufruf gespeichert. Keine Nachbesserung der Aufgaben oder Wiederholung misslungener Läufe außerhalb des festgelegten Protokolls.

## Die beiden Varianten

- **Jev allein:** vorhandene geprüfte Werkzeuge, keine GPT-Instanz, keine Sprachplanung, keine Entscheidungshilfe, kein neuer Werkzeugbau. Die Ausführungspolitik bleibt auch bei Wiederaufnahme gespeichert.
- **Begrenzt unterstützt:** einmal GPT-5.6 Terra Low zur Auftragsaufbereitung; anschließend Jev, bei unsicherer Auswahl höchstens eine Terra-Entscheidungshilfe. Kein Werkzeugbau. Beide GPT-Schritte werden mitgezählt.
- Gleiche vier Werkzeuge, unabhängige frische Register, wechselnde Reihenfolge der Varianten. Keine Graphhinweise und kein Zugriff auf frühere Chats. Ergebnisse werden lokal gegen festgelegte Sollwerte geprüft; diese Sollwerte sehen die Modelle nicht.

## Ergebnisse

| Prüfbereich | Jev allein | Mit begrenzter GPT-Hilfe |
|---|---:|---:|
| Vorbereitete, lösbare Datenaufgaben | 12/12 | 12/12 |
| Fehlende oder mehrdeutige Eingabe | 4/4 | 4/4 |
| Fehlendes Werkzeug korrekt melden | 2/2 | 2/2 |
| Zahlen aus Fließtext aufbereiten | 0/2 | 1/2 |
| Fehlerhaftes CSV anhalten | 2/2 | 2/2 |
| Vorübergehenden Ausführungsfehler überwinden | 0/2 | 0/2 |

Erfolgreiches Nachfragen oder Anhalten ist **kein erledigter Datenauftrag**. Bei Rückfragen wird die passende Entscheidung geprüft, nicht die sprachliche Qualität einer konkreten Rückfrage. Ein fehlgeschlagener Wiederholungsversuch bleibt ein Fehler, auch wenn das Anhalten sicher war.

| Messgröße | Jev allein | Mit begrenzter GPT-Hilfe |
|---|---:|---:|
| Läufe | 24 | 24 |
| Erfüllte fallbezogene Kriterien | 20 | 21 |
| Als erledigt abgeschlossene Aufträge | 12 | 13 |
| Falsche Abschlussbehauptungen laut Sollvergleich | 0 | 0 |
| Jev-Aufrufe | 44 | 40 |
| GPT-Aufrufe inklusive Planung | 0 | 24 |
| Median aller Läufe | 1.63 s | 10.81 s |
| Median der vorbereiteten lösbaren Aufgaben | 2.19 s | 12.09 s |

Alle Zeiten umfassen die vollständige Ausführung des jeweiligen Falls inklusive GPT-Vorbereitung, eventueller Entscheidungshilfe, Jev-Aufrufen, Werkzeugausführung und Sollvergleich. Die gemeinsame Werkzeugprüfung vor dem Experiment ist ausgeschlossen. Der Median aller Läufe vermischt Antworten und frühe Stopps; für Geschwindigkeit ist deshalb der Vergleich der lösbaren Datenaufgaben aussagekräftiger.

## Was die Beobachtungen bedeuten

**Jev hat den vorhandenen Werkzeugpfad tatsächlich selbst gesteuert:** 12/12 lösbare,
vorbereitete Datenaufgaben gelangen ohne GPT. Der Median lag bei 2,19 Sekunden, mit
vorgeschalteter GPT-Aufbereitung bei 12,09 Sekunden. Die unterstützte Variante machte
24 GPT-Aufrufe, alle zur Vorbereitung, und benötigte in diesem Lauf keine zusätzliche
GPT-Entscheidungsprüfung. Die Referenz ist unser konkreter hybrider Aufbau, kein
isolierter Geschwindigkeitsvergleich der Modelle.

Bei fehlenden Daten oder nicht gewähltem Datensatz löste Jev 4/4 passende Rückfragen
aus. In der unterstützten Variante beantwortete GPT diese vier Fälle bereits durch
eine Rückfrage, bevor Jev aufgerufen wurde. Eine weitere GPT-Rückfrage betraf das
fehlerhafte CSV. Damit sind fünf unterstützte Läufe vollständig in der Vorbereitung
angehalten worden; sie werden nicht als Jev-Leistung ausgegeben.

**Fließtext blieb eine Grenze:** Jev allein blieb zweimal wegen unsicherer Auswahl
stehen. GPT bereitete einmal sämtliche Zahlen korrekt auf. Beim zweiten Versuch gab
GPT bereits die gefilterten Werte `[11, 4]` statt der vollständigen Eingabe
`[-6, 11, 0, 4, -2]` zurück. Das ist keine nachgewiesene falsche Rechnung. Es verletzt
aber die vorab festgelegte Rollenabgrenzung, weil GPT damit schon den fachlichen
Filterschritt erledigt. Die lokale Prüfung stoppte diesen Lauf; er zählt deshalb als
nicht bestanden. Der Planer war nicht speziell auf diese zusätzliche Transkriptions-
Beschränkung optimiert. Das Ergebnis beschreibt die vorhandene Anbindung.

**Fehlerbehebung fehlt im Harness:** Bei der einmaligen simulierten Worker-Störung
hielten beide Varianten in beiden Wiederholungen an. Nach einem Werkzeugfehler sperrt
das bestehende Harness das Werkzeug und bietet Jev in diesem Prüfmodus keine Wiederholung
an. Der Fall testet dadurch die aktuelle Gesamtfähigkeit des Systems; er belegt nicht,
dass Jev eine angebotene Wiederholung falsch auswählen würde. Auch GPT konnte diesen
fehlenden Ausführungspfad nicht ersetzen.

Kein Lauf wurde fälschlich als erledigt bewertet. Das ist eine Beobachtung an diesem
kleinen Testset, keine allgemeine Garantie. Der nächste sachlich begründete Ausbau ist
eine nachweisbar reine Eingabeaufbereitung sowie eine begrenzte Wiederholung eindeutig
vorübergehender Fehler, bevor die Zahl der Agenten oder Werkzeuge vergrößert wird.

## Jeder einzelne Fall

| Fall | Jev allein: Wiederholung 1 / 2 | Unterstützt: Wiederholung 1 / 2 |
|---|---|---|
| sort_decimals | ✓ completed (1.70 s; GPT 0) / ✓ completed (1.82 s; GPT 0) | ✓ completed (11.07 s; GPT 1) / ✓ completed (11.00 s; GPT 1) |
| select_dataset | ✓ completed (1.65 s; GPT 0) / ✓ completed (1.61 s; GPT 0) | ✓ completed (10.18 s; GPT 1) / ✓ completed (9.71 s; GPT 1) |
| positive_sorted | ✓ completed (2.56 s; GPT 0) / ✓ completed (2.62 s; GPT 0) | ✓ completed (15.22 s; GPT 1) / ✓ completed (13.11 s; GPT 1) |
| positive_total | ✓ completed (2.68 s; GPT 0) / ✓ completed (2.69 s; GPT 0) | ✓ completed (11.03 s; GPT 1) / ✓ completed (10.40 s; GPT 1) |
| no_positive_values | ✓ completed (2.80 s; GPT 0) / ✓ completed (2.61 s; GPT 0) | ✓ completed (14.45 s; GPT 1) / ✓ completed (13.31 s; GPT 1) |
| csv_untrusted_text | ✓ completed (1.66 s; GPT 0) / ✓ completed (1.68 s; GPT 0) | ✓ completed (13.13 s; GPT 1) / ✓ completed (14.89 s; GPT 1) |
| missing_values | ✓ needs_input (0.72 s; GPT 0) / ✓ needs_input (0.72 s; GPT 0) | ✓ planner_clarification (6.32 s; GPT 1) / ✓ planner_clarification (6.47 s; GPT 1) |
| ambiguous_dataset | ✓ needs_input (0.84 s; GPT 0) / ✓ needs_input (0.73 s; GPT 0) | ✓ planner_clarification (8.08 s; GPT 1) / ✓ planner_clarification (7.46 s; GPT 1) |
| missing_tool | ✓ needs_capability (1.60 s; GPT 0) / ✓ needs_capability (1.79 s; GPT 0) | ✓ needs_capability (12.23 s; GPT 1) / ✓ needs_capability (9.38 s; GPT 1) |
| prose_input | ✗ needs_input (0.82 s; GPT 0) / ✗ needs_input (0.74 s; GPT 0) | ✓ completed (13.92 s; GPT 1) / ✗ evaluation_error (9.89 s; GPT 1) |
| malformed_csv | ✓ failed (1.04 s; GPT 0) / ✓ failed (0.95 s; GPT 0) | ✓ planner_clarification (9.50 s; GPT 1) / ✓ failed (11.79 s; GPT 1) |
| transient_worker_failure | ✗ failed (0.82 s; GPT 0) / ✗ failed (0.74 s; GPT 0) | ✗ failed (9.40 s; GPT 1) / ✗ failed (10.61 s; GPT 1) |

## Aussagegrenzen

Vier kleine Datenwerkzeuge und zwölf synthetische Fälle sind keine allgemeine Agentenprüfung. Es wurden weder offene Recherche, Browserbedienung, Chatgedächtnis, Schwärme noch selbstständiges Erlernen neuer Werkzeuge geprüft. Zwei Wiederholungen erlauben keine belastbare Schätzung allgemeiner Zuverlässigkeit.

Die unterstützte Variante führt bewusst immer einen Planungsschritt aus. Sie misst den Nutzen und Aufwand dieser konkreten Architektur, nicht die schnellstmögliche GPT-Anbindung. Die GPT-Zeit enthält den Codex-CLI-Start. Aus diesem Vergleich folgt kein allgemeines Verhältnis der Modellgeschwindigkeiten.

Für den Fließtextfall darf die Planung nur die genannten Zahlen unverändert strukturieren. Eine lokale Prüfung verhindert, dass ein bereits berechnetes Ergebnis als Eingabe ausgegeben wird. Alle übrigen Eingaben und das ursprüngliche Ziel bleiben erhalten. Ein bloßer Antworttext des Planers wird nicht als erfolgreich ausgeführte Werkzeugaufgabe gewertet.

Der Ausführungsfehler wird einmal direkt vor dem Worker künstlich ausgelöst. Es erfolgt kein externer Schreibzugriff. Ein bestandener Test auf fehlerhafte Daten belegt gegebenenfalls das deterministische Anhalten des Harness, nicht eine eigenständige Fehlerdiagnose von Jev. Details stehen in den Ereignissen.

## Wiederholen

Im Projektverzeichnis, mit einem leeren Ausgabeordner und dem lokal eingerichteten Zugang:

```sh
uv run python -m casajev.autonomy_eval --output /pfad/neuer-leerer-ordner --credentials-file /pfad/typesafe.env --repeats 2
```

Eine eigene Aufgabe mit dem vorhandenen Werkzeugregister ohne GPT ausführen:

```sh
uv run casajev --home .casajev run aufgabe.json --jev-only
```

Das normale Chatfenster bleibt hybrid. Der Prüfmodus verändert oder löscht keine bestehenden Chats und ergänzt keine Schalter in der Oberfläche.

Rohdaten, Protokoll, Hashes der ausgeführten Implementierung und Softwaretests: [evidence/autonomy-20260920](evidence/autonomy-20260920). Die isolierten SQLite-Arbeitsverzeichnisse bleiben außerhalb des Auslieferungspakets.
