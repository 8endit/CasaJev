# Die Ideen hinter CasaJev

Kontextrekonstruktion am 20.09.2026 aus dem Chat **CSV Werkzeug Entwicklung**, dem
Task **TypeSafe installieren und JEV testen**, der Unterhaltung **Jev AI Nutzung**,
dem vorhandenen Verzeichnis `jev-capability-protocol` und dem hier eingefügten
Vorläufervergleich. Es wurde keine globale Neuheitsbehauptung übernommen.

| Besprochene Idee | Umsetzung in CasaJev 0.1 |
|---|---|
| Jev als aktiver Controller: beobachten, wählen, handeln, erneut beobachten | Laufende Entscheidungsschleife mit echten Werkzeugausgaben als neue Zustandsobjekte |
| Fehlende Fähigkeiten ausdrücken | Strukturierter Wunschkanal einschließlich Originalauftrag |
| Kleine Sprache statt freier Textausgabe von Jev | Choice-Fragen, Referenzen, Operationen und `other`; Codex liefert neue Bedeutungsangebote |
| Vorhandene Auswahlmöglichkeiten reichen nicht | Codex kann neue Operationen und Verträge anbieten; Jev darf alle zurückweisen |
| Spezifikation gemeinsam aushandeln | Vorlagenwahl, neue Vertragsvorschläge, bis zu zwei Revisionen, Rückfrage |
| Unklare Details dürfen einen klaren Wunsch nicht vernichten | Unsichere Hinweise bleiben null, die klare Fähigkeitsanforderung bleibt bestehen |
| Builder setzt genau den Vertrag um | Separater Bauauftrag mit Schemas, Semantik und Beispielen |
| Wiederverwendung vor Neubau | Register zuerst; nur passende Tool-Eingabe-Paare werden angeboten |
| Kleine Bausteine kombinieren | Ausgaben werden referenzierbare Eingaben weiterer Schritte; im Softwaretest geprüft |
| Triviale Aufgaben ohne Coding-Modell | Drei deterministische Vorlagen |
| Kleiner Coder normal, starkes Modell zur Eskalation | Modellkonfiguration und Reparatur-Eskalation vorhanden; Effizienzvergleich noch offen |
| Versionierung, Quellhash, Testnachweis | SQLite-Register mit Vertrags-/Quellhash und Verifier-Evidenz, alte Versionen inaktiv aufbewahrt |
| Nicht einfach Rechte ausweiten | Nur compute ist ausführbar; externe Wirkung führt zu needs_permission |
| Nach Werkzeugbau unterbrochene Aufgabe fortsetzen | Persistente Phasen und erneute Jev-Auswahl; live verifiziert |
| Einfache interaktive Bedienung | Ein Chatfeld, Antworten darüber, Dateianhänge und aufklappbarer Browser; keine technische Formularauswahl |
| Zeit/Kosten nicht blind verbrauchen | Persistente Call-/Bau-/Schrittbudgets, Prozesslimits, Token-Nutzung und gemessene Laufzeit |
| Länger effektiv arbeiten | Wiederaufnahme nach Prozessneustart; kein ungebremster Endlosmodus |
| Freie Textgenerierung an anderes Modell auslagern | Jev wählt die Gesprächsroute; Codex formuliert Antworten und Zusammenfassungen aus bereitgestelltem Kontext |
| Computer, Browser und Anwendungen bedienen | Eingebauter Chromium-Browser für manuelle Navigation, Klicks, Scrollen, Tippen und Seitenübergabe an den Chat; keine freie autonome Desktopsteuerung |
| Kalender, C-entron, Rechnungen, OAuth, Benachrichtigungen | Konkrete Connectoren und Berechtigungsverträge fehlen noch |
| Echte Aufgaben über viele Domänen bewerten | Erste drei Aufgabentypen, darunter zwei mit Wiederverwendung; kein breiter Benchmark |

## Wichtige technische Entscheidungen

**Auswahlpaare statt unabhängiger Tool-/Input-Felder.** Der erste Prototyp hatte
bereits zwischen Eingabe- und Fokusreferenz unterschieden. CasaJev geht für tatsächliche
Aufrufe weiter: Ein Kandidat enthält beides. Vorher prüft normaler Code Eingabeschema,
Datentyp und Rechte. Damit kann eine modellseitige Kreuzkombination gar nicht ausgeführt
werden.

**Ein Vertrag ist mehr als ein Wunsch.** Operation und Ergebnisart allein bestimmen
keine Implementierung. Das Originalziel, Eingaben, Rechte, Beispiele und präzise
Semantik bleiben Teil des Prozesses. Der Builder kann neue Begriffe vorschlagen,
aber das ist keine freie Sprache, die Jev selbst erfunden hätte.

**Modellentscheidung ist keine Berechtigung.** Selbst eine Jev-Antwort mit hoher
Konfidenz kann keine zusätzlichen Rechte aktivieren. Ausführung und Registrierung
liegen beim Harness. Die aktuelle Version beschränkt den automatischen Ausbau auf
reine Datenwerkzeuge.

**Ein Ergebnis ist noch kein allgemeiner Erfolgsbeweis.** Codex schreibt in einem
Aufruf den Vertrag samt Beispielen und in einem weiteren den Code. Der Verifier ist
separater Programmcode. Für eine unabhängige Zielkontrolle braucht es darüber hinaus
lokale Sollwerte oder einen domänenspezifischen Prüfer.

## Nächste produktrelevante Ausbauten

1. Einen konkreten Arbeitsbereich anschließen, etwa einen freigegebenen Dateiordner
   oder eine Test-Webanwendung, mit beobachtbarem Endzustand und eng begrenzten Rechten.
2. Den Builder-Modellmix auf einer vorab festgelegten, zurückgehaltenen Aufgabenmenge
   vergleichen. Qualität, Reparaturrate und gesamte Baukosten erfassen.
3. Registry-Suche und zusammengesetzte Abläufe für deutlich mehr Werkzeuge skalieren.
4. Einen isolierten VM-/Container-Worker für weitere Betriebssysteme ergänzen.

Das sind weitere Produktarbeiten, keine als bereits vorhanden ausgegebenen Funktionen.


## Ergänzung am 20.09.2026: Graphify für Arbeitsabläufe

Der Nutzer hat die im nicht abrufbaren Seitenchat diskutierte Idee konkretisiert:
Graphify soll helfen, Jevs Arbeitsabläufe zu konstruieren. Implementiert ist eine
erste quellengestützte Fassung: aktuelles Toolregister → Datenarten und mögliche
Verbindungen → beobachtete erfolgreiche Datenflüsse → kompakte Hinweise an Jev.
Vermutete Typkompatibilität und tatsächlich ausgeführte Verbindungen bleiben getrennt.
Der Graph ersetzt weder den Toolvertrag noch Schema-/Rechteprüfung und Ergebnisbeleg.
Er wird als Graphify-kompatibles JSON exportiert; die Graphify-CLI kann ihn abfragen.

Die ursprüngliche Seitenchat-Antwort lag nicht vollständig vor. Diese Umsetzung folgt
der hier bestätigten Zielrichtung, nicht einer behaupteten wortgetreuen Rekonstruktion.
Ein Vergleich mit/ohne Graph ist Teil des neuen Pilots in VERGLEICH.md. Größere
Register, langfristige Wiedererkennung und tiefe Workflow-Synthese sind weiter offen.
