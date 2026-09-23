# CasaJev: erster Vergleich mit Terra und Sol

Gemessen am 20.09.2026 auf diesem Mac, mit echten Provideraufrufen. Kleine lokale
Pilotmessung, keine Aussage darüber, welches Modell allgemein der beste Agent ist.

## Ergebnis mit vorhandenen Werkzeugen

Sechs Aufgaben: je zwei unterschiedliche Eingaben für Zahlensortierung, exakte
CSV-Dubletten und die Kette „positive Zahlen filtern → summieren“. Vier identische
Werkzeuge mit denselben Implementierungen und derselben beschränkten Python-Ausführung.
Alle Sollwerte wurden vor dem Lauf festgelegt und nicht an die Modelle übergeben.

| Aufbau | Median pro Aufgabe | Inhalt richtig | Direkt im geforderten Zielformat |
|---|---:|---:|---:|
| Jev 1.13.0 + vorhandene Tools + Graphhinweise | **1,80 s** | 6/6 | 6/6 |
| Terra Low, ein durchgehender Codex-Agentenlauf mit denselben Tools über MCP | **16,84 s** | 6/6 | 6/6 |
| Sol Low, ein durchgehender Codex-Agentenlauf mit denselben Tools über MCP | **13,01 s** | 6/6 | 4/6 |
| Festes Skript, Operation bereits vorgegeben | **0,18 s** | 6/6 | 6/6 |

Bei Sol waren beide Sortierergebnisse richtig, aber in eine MCP-Transporthülle
verpackt. Der ursprüngliche strikte Vergleich zählt sie als Formatfehler. Eine
zusätzliche, rein mechanische Auswertung dekodiert das einzelne JSON-Textfeld aus
`{content:[{type:"text",text:"…"}],isError:false}`. Danach stimmen auch diese beiden
Inhalte. **Keine erneute Modellanfrage und keine inhaltliche Korrektur.** Originale
und ergänzende Auswertung bleiben getrennt erhalten. Die Mediane in der Tabelle
verwenden alle sechs Laufzeiten, also auch die beiden Formatfälle.

Diese Anbindung zeigt für die getesteten kleinen Aufgaben einen deutlichen
Latenzvorteil von Jev. Das Skript zeigt zugleich: Eine bereits fest programmierte
Operation benötigt überhaupt keine Modellentscheidung und ist noch schneller.

## Kontrollierter Austausch des Entscheiders

Zusätzlich wurde derselbe CasaJev-Entscheidungszyklus mit identischen Zuständen,
Auswahloptionen, Graphhinweisen, Stop-Regeln und Werkzeugen gemessen. Anstelle der
Jev-API wählt Terra beziehungsweise Sol die nächste Aktion per strukturierter Antwort.
Alle drei Varianten bestehen 6/6 Sollvergleiche.

| Entscheider im identischen Harness | Median |
|---|---:|
| Jev | 1,80 s |
| Terra Low | 13,13 s |
| Sol Low | 12,12 s |

Hier startet die Codex-CLI **für jede Entscheidung neu**, während Jev direkt per HTTP
aufgerufen wird. Das ist ein Anbindungsnachteil, kein isolierter Modellvergleich.
Deshalb enthält der Hauptvergleich oben zusätzlich die durchgehenden Agentenläufe
mit nur einem CLI-Start pro Aufgabe und echten MCP-Werkzeugaufrufen.

## Bringt der Graph bereits Geschwindigkeit?

| Jev-Variante | Median | Richtige Ergebnisse |
|---|---:|---:|
| Mit Graphhinweisen | 1,80 s | 6/6 |
| Ohne Graphhinweise | 1,77 s | 6/6 |

**In diesem Pilot kein nachgewiesener Zusatznutzen durch den Graphen.** Vier Tools
und eine Kette aus zwei Schritten sind auch ohne Graph gut überschaubar. Die
Graphstruktur, echte Datenflusskanten und Abfrage per installierter Graphify-CLI
funktionieren. Ein Nutzen bei großen Registern, längeren Ketten oder Wiedererkennung
muss gesondert getestet werden. Vermutete Typkompatibilität ist keine bewiesene
fachliche Eignung eines Ablaufs.

## Was genau gemessen wurde

- Gesamtdauer vom lokalen Start bis zur Rückgabe und Sollprüfung: Providerlatenz,
  CLI-Start, Protokoll, Werkzeugausführung und Abschlussentscheidung eingeschlossen.
- Die native MCP-Vergleichsgruppe wurde nach der Controller-Gruppe gemessen; innerhalb
  einer Gruppe wechselte die Modellreihenfolge. Keine parallelen Benchmark-Provideraufrufe.
  Keine Garantie für identische Serverlast, keine Isolierung von normaler Mac-Hintergrundlast.
- Jev war fest auf `jev-1.13.0`, Terra auf `gpt-5.6-terra`, Sol auf `gpt-5.6-sol` gesetzt.
  Terra und Sol nutzten jeweils `low`. Unterschiede in Modellprotokollen und Prompts
  bleiben; Jev verwendet Konfidenzschwellen, die generativen Modelle strukturierte Auswahl.
- Die sechs Inputs waren vorbereitete synthetische Aufgaben, keine zufällige Auswahl
  realer Nutzeraufgaben. Verträge und Beispiele der vorhandenen Werkzeuge waren sichtbar,
  die unabhängigen Sollwerte nicht. Kein Werkzeugbau im Zeitvergleich.
- Bei zusammengesetzten Aufgaben verwenden die drei Agenten zwei Werkzeuge. Die
  Skriptuntergrenze kennt den Auftrag bereits und kombiniert diese Operation direkt.
- Kein Vergleich für Recherche, Schreiben, komplexe Desktopbedienung oder neue
  Toolentwicklung. CasaJev nutzt für freie Texte/Recherche selbst Terra; Jevs schneller
  Werkzeugpfad darf nicht als Geschwindigkeit des gesamten Assistenten ausgegeben werden.
- Keine Preisberechnung. Provider-Tokenangaben werden gespeichert, sind aber nicht über
  verschiedene Modellfamilien hinweg ein direkter Kostenmaßstab.

Die Modellkennungen und lokale MCP-Konfiguration wurden anhand der offiziellen
[Modelldokumentation](https://learn.chatgpt.com/docs/models) und
[MCP-Dokumentation](https://learn.chatgpt.com/docs/extend/mcp) abgeglichen;
Verfügbarkeit und Aufrufe wurden hier tatsächlich getestet.

## Reproduzieren und Rohdaten

`evidence/benchmark-20260920/` enthält Protokoll, feste Eingaben, ursprüngliche
Ergebnisse, Controller-Ereignisse inklusive Providerantworten, native MCP-Aufrufe und
die getrennte Transportauswertung. `workflow-example.json` ist ein tatsächlicher
Ablaufgraph der positiven Summe; `EXTRACTED` und `INFERRED` bleiben unterscheidbar.

Aus dem Projektverzeichnis, mit neuen Ausgabeordnern:

```sh
uv run python -m casajev.benchmark --output ../../work/neuer-vergleich --credentials-file /pfad/typesafe.env
uv run python -m casajev.benchmark_native --output ../../work/neuer-nativer-vergleich
```

Die Programme überschreiben keinen schon vorhandenen Ergebnislauf. Graphhinweise
lassen sich im Harness über `use_graph=False` abschalten. Die Befehle machen echte
Provideraufrufe und nutzen die bestehende Anmeldung.
