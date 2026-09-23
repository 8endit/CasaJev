# CasaJev 0.2 — Ausbau und Live-Prüfung

Stand 20.09.2026. **77 Softwaretests bestanden in 19,42 Sekunden.**
Aktueller Lauf: `evidence/autonomy-20260920/software-tests.txt`.
Zusätzlich 48 echte Providerläufe zum getrennten Jev-Betrieb; Ergebnisse und Grenzen
stehen in [AUTONOMIE-TEST.md](AUTONOMIE-TEST.md).
Chatverlauf über Neuer Chat und Seitenneuladen hinweg live geprüft. Der Button
Chats öffnet auch ältere gespeicherte Gespräche. Die Browseransicht wird jetzt auf
Wunsch geöffnet; Hintergrundarbeit bleibt möglich.
Der vorherige Ausbau umfasste 56 bestandene Tests in 21,27 Sekunden.
Nachweise in `evidence/expanded-20260920/`. Der separate Geschwindigkeitsvergleich
mit Jev, Terra, Sol, Skriptuntergrenze und Graph-Abschaltung steht in [VERGLEICH.md](VERGLEICH.md).

Zusätzliche Regressionstests prüfen Gesprächskontext bei unsicheren Routen,
Routing-Ausfall, echte Suchevidenz, URL-Zusammenfassung, Grenzen für externe Aktionen,
Bindung zusammengehöriger Operanden, neue Werte in Folgefragen, Ausblenden unbestätigter
Zwischenergebnisse, einmalige Entscheidungsprüfung sowie die Graph-Herkunft und den
Ausschluss geänderter/gesperrter Tools. Die MCP-Testwerkzeuge verwenden denselben Runner.

## Sichtbarer Browser

Die Browseransicht öffnet sich beim Auftrag automatisch und fragt bei sichtbarem Tab
bis zu zweimal pro Sekunde ein aktuelles Bild ab. Direkte Navigation statt simulierter
Mausbewegung; keine künstliche Verzögerung für die Darstellung. Zwölf zusätzliche
Tests prüfen Sucherkennung, ausschließlich beobachtete Zieladressen, unsichere/ungültige
Entscheidungen, fehlende Ergebnisse und das Anhalten an Googles Zugriffsprüfung.

- Sichtbarer Auftrag „Google IANA example domains und lies die offizielle Quelle“:
  Google verlangte ein CAPTCHA. Nach 3,1 s Browserzeit und 3,9 s insgesamt angehalten,
  keine Quelle gelesen und keine Zusammenfassung erfunden. Der initial noch allgemeine
  Hinweis auf fehlende Treffer wurde anschließend um eine konkrete CAPTCHA-Erkennung
  ergänzt. Diese Erkennung wurde per Regressionstest geprüft, nicht durch erneutes
  Aufrufen des CAPTCHAs.
- Anschließend example.com per Chat geöffnet und tatsächlich gelesen: **0,2 s Browserzeit,
  7,2 s einschließlich Antwort**. Die Zusammenfassung entsprach dem sichtbaren Inhalt,
  ein Quellenlink wurde angezeigt. Rohzeiten und Testnachweise liegen unter
  `evidence/browser-visible-20260920/`.

Die vollständige Auswahl eines Google-Treffers wurde nur mit kontrollierten Testdaten
geprüft; Googles Live-Sperre bleibt bestehen. Diese zwei Einzelfälle sind kein
Browser-Benchmark und messen auch nicht den Zusatzaufwand der Live-Ansicht gegenüber
einem Lauf ohne Anzeige. Die bisherigen Jev/Terra/Sol-Vergleiche betreffen vorbereitete
Datenwerkzeuge, nicht autonome Browseraufgaben. Bestellungen sind nicht implementiert.

## Reale Alltagstests

| Auftrag | Beobachtetes Ergebnis | Zeit im Chat |
|---|---|---:|
| Aktueller Bundeskanzler mit offizieller Quelle | Live-Suche; aktuelle Regierungsquellen und verlinkte Antwort | 29,08 s |
| Folgefrage „Nur den Namen bitte“ | „Friedrich Merz“, keine erneute Rückfrageschleife | 7,19 s |
| Übersetzung einer Terminverschiebung | Passende englische Übersetzung | 6,58 s |
| „Etwas formeller bitte“ | Passende Überarbeitung mit erhaltenem Kontext | 8,46 s |
| example.com lesen und in einem Satz zusammenfassen | Inhalt tatsächlich aus Chromium gelesen und zusammengefasst | 9,85 s |
| „Auf Englisch bitte“ | Vorherige Zusammenfassung korrekt übersetzt | 9,23 s |
| Positive Zahlen filtern und summieren | 11, zwei vorhandene Werkzeuge kombiniert | 3,47 s |
| Kundendaten fehlen | Gezielte Bitte um die Kundendaten statt generischer Ergebnisfrage | 8,40 s |
| Terminabsage in zwei Sätzen | Passender Textentwurf; nichts versendet | 8,79 s |
| 19 Prozent von 249 nach Korrektur, erstmals gebaut | 47,31; Werkzeugbau mit Reparatur und Entscheidungsprüfung | 57,02 s |
| Derselbe Prozentauftrag, vorhandenes Tool | 47,31; kein erneuter Bau | 25,17 s |
| Folgefrage: 7 Prozent von 320 | 22,4; neue Werte, dasselbe registrierte Werkzeug, kein erneuter Bau | 10,76 s |

Die Chatzeiten umfassen auch Sprachplanung/Argumentaufbereitung. Sie sind ausdrücklich
nicht mit den kürzeren Zeiten für vorbereitete Tool-Aufgaben gleichzusetzen. Texte,
Recherche und sprachliche Argumentaufbereitung stammen vom Codex-Sprachmodell.

Zusätzlich wurde die ursprüngliche Bundeskanzler-Frage über das sichtbare Chatfeld
abgeschickt. Die Antwort erschien mit anklickbaren offiziellen Quellen und 36,7 s
Bearbeitungszeit. Ein Quellenklick öffnet die Browseransicht. Die Kernoberfläche
bleibt ein Chatfeld mit Antworten darüber.

## Tatsächlich gefundene Fehler

Die erste Prozentaufgabe blieb stehen: zwei getrennte Operanden passten nicht zum
Ein-Objekt-Vertrag des vorgeschlagenen Tools. Die nachfolgende alte Übergabe konnte
bei neuen Zahlen noch ein altes Objekt verwenden. Beide Fehlverläufe wurden erhalten.
Jetzt werden zusammengehörige Operanden gebündelt, Folgefragen mit neuen Werten neu
aufbereitet und vorhandene Eingabeschemas zur Wiederverwendung berücksichtigt.
Die abschließenden Live-Werte 47,31 und 22,4 stimmen; die beiden letzten Aufgaben
benötigten jeweils null Bau- und null Builder-Aufrufe im Werkzeug-Harness.
Die separate Sprachplanung ist dabei nicht als Builder-Aufruf mitgezählt.

Ein einmaliger Review kann eine gültige, aber unsichere Jev-Entscheidung auflösen.
Er bleibt innerhalb der vorhandenen Auswahl und Budgets; Abschluss ohne Beobachtungen
wird weiterhin abgewiesen. Ungültige Jev-Antworten werden nicht als Erlaubnis ausgelegt.
Nicht bestätigte Zwischenwerte werden in der Oberfläche nicht mehr als Ergebnis gezeigt.

Der Graph speichert beobachtete Datenflüsse mit Quellenreferenzen und trennt sie von
vermuteter Typkompatibilität. Eine echte Graphify-Abfrage des exportierten Graphen
funktioniert. Ein zusätzlicher Leistungsnutzen ist in den sechs kleinen Testaufgaben
nicht nachgewiesen. Die Softwaretests und Einzelfälle sind keine allgemeine
Zuverlässigkeitsgarantie und keine umfassende Sicherheitsprüfung.

---

## Archiv: erster Entwicklungsstand

# CasaJev — tatsächlich geprüft

Stand: 20.09.2026. Lokaler Entwicklungsstand, synthetische Daten; kein unabhängiger
Vergleichsbenchmark und keine allgemeine Zuverlässigkeitszusage.

## Softwaretests

**38 Tests bestanden**, zuletzt in 15,42 Sekunden. Nachweis:
`evidence/software-tests.txt`.

Abgedeckt sind vollständiger Rundlauf, dauerhafte Wiederverwendung, Neustart in der
Prüfphase, unveränderliche Budgets, falsche Abschlussmeldungen, unabhängiger Sollvergleich,
veralteter Zustand, konkurrierende Worker, Rechteüberschreitung, unzulässige Schemas,
Quelltextfilter, CPU-/Zeit-/Ausgabegrenzen, korrumpierte Registrierungen,
Versionswechsel, Werkzeugkomposition, Reparatur sowie HTTP-Origin-/Host-Prüfung.

Die Betriebssystemgrenzen wurden **zusätzlich unter Umgehung des Quelltextfilters**
getestet: ein Testprogramm konnte weder eine Benutzer-/Temp-Datei lesen, eine Datei
schreiben noch eine Netzwerkverbindung öffnen. Das ist konkrete Testevidenz für diese
Operationen, keine umfassende Sicherheitsprüfung des macOS-Workers.

Neu nach der UI-Korrektur: Ein-Nachricht-Eingaben, CSV/JSON-Erkennung, Dateianhänge,
Webseitenkontext, Gesprächsfortsetzung und Browser-URL-Prüfung.

## Echte Jev-/Codex-Läufe

| Auftrag | Ergebnis | Bauversuche | Codex-Aufrufe | Laufzeit |
|---|---|---:|---:|---:|
| CSV-Dubletten, leeres Register | Exakter Sollwert erreicht; Vorlage geprüft und registriert | 1 | 0 | 4,19 s |
| Kategoriesummen, fehlende Fähigkeit | Vertrag von Codex vorgeschlagen, von Jev ausgewählt, von Codex implementiert; Sollwert erreicht | 1 | 2 | 29,29 s |
| Andere CSV mit Kommata und abweichenden Schreibweisen | Vorhandenes Werkzeug; exakter neuer Sollwert erreicht | 0 | 0 | 1,81 s |
| Andere Kategoriesummen mit Nullsummen und Leerzeichen | Vorhandenes Werkzeug; exakter neuer Sollwert erreicht | 0 | 0 | 2,07 s |
| Zahlen sortieren über erste Oberfläche | Richtige Ausgabe; beim Abschluss zunächst angehalten, nach Korrektur und Wiederaufnahme abgeschlossen | 1 | 0 | 4,51 s aktive Gesamtlaufzeit |
| Andere Zahlen über erste Oberfläche | Richtige Ausgabe, direkte Wiederverwendung | 0 | 0 | 2,79 s |
| Eine einzelne Chatnachricht mit Zahlen | Eingabe automatisch erkannt, Werkzeug wiederverwendet, richtige Ausgabe im Chat | 0 | 0 | 1,90 s Werkzeug-Harness, plus Gesprächsrouting |

Die ersten vier Aufgaben hatten **vor dem jeweiligen Lauf lokal hinterlegte Sollwerte**,
die weder an Jev noch an Codex übertragen wurden. Bei den drei Oberflächenaufgaben
wurde die sichtbare Ausgabe separat geprüft. Deren UI behauptet keinen unabhängigen
maschinellen Sollvergleich.

Die Laufzeiten enthalten die jeweilige Entscheidungsschleife, Werkzeugausführung
und gegebenenfalls Vertrags-/Bauaufrufe. Es sind einzelne, unterschiedliche Eingaben;
der Vergleich 29,29 s zu 2,07 s belegt einen konkreten Wiederverwendungsfall, keine
statistisch abgesicherte Beschleunigung. Codex-Token-Nutzung und Jev-Modellantworten
stehen in `evidence/live-runs.json`. Preise wurden nicht geschätzt.

## Gefundener Fehler und Korrektur

Beim ersten Sortierlauf war die Werkzeugausgabe richtig; die Dekodierung eines
späteren Jev-Antwortpakets meldete inkonsistente Wahrscheinlichkeiten. Der alte Parser
brach bei jedem fehlerhaften Feld ab, auch bei unbenutzten Zusatzfragen. Er speicherte
die fehlgeschlagene Rohantwort noch nicht, sodass dieses konkrete Feld im ersten
Fehlerfall nachträglich nicht sicher bestimmt werden kann.

Jetzt werden optionale Hinweise getrennt geprüft. Ein fehlerhafter Hinweis wird als
ungeklärt protokolliert; ein ungültiger Hauptentscheid bleibt gesperrt. Fehlerhafte
Hauptantworten werden samt Rohantwort gespeichert. Zwei Regressionstests prüfen
beides. Die angehaltene Aufgabe konnte ohne erneuten Werkzeugbau fortgesetzt werden.

## Chat und integrierter Browser

Über die tatsächlich bediente Oberfläche geprüft:

- Genau ein Chat-Eingabefeld, keine Datentyp-Auswahl und keine Beispielschaltflächen.
- Nachricht „Sortiere diese Zahlen aufsteigend: [8, 3, -1, 8, 0]“ führt zu
  `[-1, 0, 3, 8, 8]` direkt über dem Eingabefeld.
- `example.com` lädt in der eingebauten Chromium-Ansicht.
- Ein Klick auf „Learn more“ navigiert tatsächlich zur IANA-Seite.
- „Seite im Chat verwenden“ hängt den gelesenen Inhalt an die nächste Nachricht.
- Die Bitte um zwei kurze Sätze führt zu einer sachlich passenden Antwort im Chat.
- Auf der Wikipedia-Startseite wurde „test“ erfolgreich in das echte Suchfeld eingegeben.

Der Browser ist eine lokale, interaktive Chromium-Bildansicht mit eigener Sitzung.
Mehrstufige autonome Webrecherche, beliebige externe Aktionen und ein vollständiger
Ersatz für alle Funktionen eines normalen Desktopbrowsers sind nicht nachgewiesen.

## Dateien

- `evidence/live-runs.json`: Aufgaben, Entscheidungen, Verträge, Prüfung und Ergebnisse.
- `evidence/registry.json`: tatsächlich registrierte Werkzeuge inklusive Code/Hashes.
- `evidence/chat-tests.json`: gekürzte Chat-Testverläufe ohne rohe Webseitenkopien.
- `evidence/software-tests.txt`: letzter vollständiger Testlauf.
