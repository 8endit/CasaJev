# CasaJev 0.5.1

**Ein Zuhause für Fähigkeiten.** Begrenztes Entscheidungs-Harness mit Jev für den
allgemeinen Werkzeugpfad, lokalem Laya für geprüfte kleine Echtzeit-Aktionsräume und
einer Codex-Werkstatt außerhalb des Echtzeitpfads.

Jev entscheidet im allgemeinen Harness, was als Nächstes hilft. Fehlt eine Fähigkeit, handelt CasaJev einen
Werkzeugvertrag aus, baut und prüft eine Implementierung, registriert sie und setzt
denselben Auftrag fort. Ein späterer Auftrag kann das Werkzeug direkt verwenden.

**Projektstatus:** Experimenteller lokaler Prototyp unter Apache-2.0. Die bisherigen
Geschwindigkeitswerte stammen aus kleinen synthetischen Tests und belegen keinen
allgemeinen Vorteil gegenüber GPT. Beiträge und reproduzierbare Gegenbeispiele sind
willkommen; siehe [CONTRIBUTING.md](CONTRIBUTING.md).

## Start

### Desktop auf macOS

Die bevorzugte macOS-Ausgabe ist `CasaJev.app`. Sie enthält ein einziges sichtbares
Chromium-WebView: Der Nutzer sieht rechts genau die Seite, die der Aktionsmodus
beobachtet und steuert. Ein zweiter versteckter Playwright-Browser und der frühere
Screenshot-Stream entfallen. Der Python-Kern läuft weiterhin lokal und bindet sich
an einen zufälligen Loopback-Port. Seine Desktop-Befehle sind durch ein zufälliges
Sitzungstoken geschützt.

Die Desktop-Daten liegen unter `~/Library/Application Support/CasaJev/state`. Die
Entwicklungsversion wird mit `CasaJev entwickeln.command` oder `cd desktop && npm run dev`
gestartet. Python-/Electron-Änderungen starten die Entwicklungs-App automatisch neu;
Oberflächenänderungen werden direkt neu geladen. Wheel, ZIP und App-Paket werden erst
für eine Weitergabe mit `npm run package:mac` gebaut. Benötigt bleiben `uv`, die
Codex-CLI-Anmeldung und für Jev der lokale TypeSafe-Schlüssel. Das aktuelle Bundle ist
lokal/ad-hoc signiert, aber noch nicht mit einem Apple-Developer-Zertifikat notarisiert.

### Lokale Web- und plattformübergreifende Version

Auf macOS `CasaJev starten.command` doppelklicken. Unter Linux im Projektordner
`./start-casajev.sh` ausführen. Unter Windows `Start-CasaJev.ps1` mit PowerShell
ausführen. Danach öffnet sich **http://127.0.0.1:8787**.

Für die native Desktop-Oberfläche unter Windows `Start-CasaJev-Desktop.ps1` mit
PowerShell ausführen. Docker Desktop muss zuvor laufen. Der Starter richtet die
Python- und Desktop-Abhängigkeiten ein und öffnet das Electron-Fenster.
Der Web-Starter speichert Chats und Zugangsdaten standardmäßig im privaten
Windows-Benutzerordner unter `%LOCALAPPDATA%\CasaJev\state`.

Beim ersten Start fragt CasaJev getrennt nach dem Provider für allgemeine Aufgaben und
für die Echtzeit-Pipeline. Die evidenzbasierte Voreinstellung ist **Jev allgemein** und
**Laya für vorher geprüfte kleine Echtzeit-Aktionsräume**. Die Auswahl ist später unter
**Einstellungen** änderbar und lädt Laya nicht bereits durch das Auswählen in den Speicher.

Auf Windows und Linux benötigt die geprüfte Werkzeugausführung Docker Desktop oder
Docker Engine. Der Worker läuft dort ohne Netzwerk, read-only, ohne Linux-Capabilities
und mit CPU-, Speicher-, Prozess- und Ausgabelimits. CasaJev führt bei fehlender Sandbox
keinen unsicheren Fallback aus. Der native macOS-Pfad verwendet weiterhin Seatbelt.

Der TypeSafe-Schlüssel wird lokal eingerichtet und nicht im Quellcode gespeichert.
Codex verwendet eine vorhandene CLI-Anmeldung. Falls die Anwendung bereits läuft, genügt die Browseradresse.
Zum Beenden im Server-Terminal Strg+C drücken. Es ist kein Autostartdienst eingerichtet.

Die vier Standardwerkzeuge werden beim Live-Start geprüft und bereitgestellt. Der
optionale lokale Laya-Pfad lädt einen fest auf eine geprüfte Revision gesetzten Checkpoint
und hält ihn danach vorgewärmt. Ein kleiner Drei-Aktionen-Test lag auf dem getesteten
Intel-Mac bei rund 201 ms Median und 206 ms P95. Der allgemeinere Acht-Aktionen-Routingtest
war mit 3,14 s Median und 1/8 richtigen Entscheidungen klar ungeeignet; deshalb ist Laya
nicht der ungeprüfte Standardersatz für Jev.

Die Oberfläche ist ein Chat: **eine Eingabe unten, Antworten darüber**. Es gibt keine
Datentyp-Auswahl, Vorlagenknöpfe oder Werkzeugkarten. JSON/CSV lassen sich direkt in
die Nachricht einfügen; Dateien über die Büroklammer oder per Drag-and-drop anhängen.
Gespräche, Aufgaben und Werkzeuge bleiben in `.casajev/state.sqlite3` beziehungsweise
im oben genannten Desktop-Datenordner gespeichert.
Die einklappbare Seitenleiste enthält Chats mit Volltextsuche, Umbenennen, Anheften und Archiv. Das Menü oben bleibt als kurzer Verlauf verfügbar.
**Neuer Chat** startet ein zusätzliches Gespräch; vorhandene Verläufe bleiben erhalten.

**Browser** öffnet rechts eine echte lokale Chromium-Sitzung. Adresse eingeben,
Webseite anklicken, scrollen und Text tippen. Mit **Seite im Chat verwenden** wird der
sichtbare Seiteninhalt als Anhang für die nächste Nachricht übernommen. Erst das
Absenden übergibt diesen Inhalt an die Modelle. Eine ausdrückliche Nachricht wie
„Öffne https://example.com“ öffnet die Adresse ebenfalls. Die Browserdarstellung ist
eine interaktive Live-Bildansicht, kein iframe; die tatsächliche Website läuft in
Chromium. Cookies, Local Storage und IndexedDB werden auf Wunsch lokal gespeichert und beim Neustart geladen. Session Storage und die vollständige Tab-Historie sind nicht enthalten. Unter Accounts lässt sich die gespeicherte Sitzung löschen.
Downloads, Datei-Uploads auf Websites, Medien und komplexe Browserdialoge sind nicht
als vollständiger Browser-Ersatz ausgearbeitet.

Ausdrückliche Bedienaufträge wie „klicke …“, „fülle … aus“ oder „spiele …“ laufen
über den **Aktionsmodus**. Codex erzeugt dabei keine unbeschränkten Shell-Befehle,
sondern kurze, typisierte Browserbefehle aus einem festen Satz: öffnen, klicken,
Maus bewegen, Maustaste halten/lösen, scrollen, Text, unterstützte Tasten und kurz
warten. Lokale Mauspfade und Tastenfolgen steuern Canvas-Spiele zwischen zwei
Kontrollbildern flüssig weiter. CasaJev führt diese Befehle aus und beobachtet die
Seite danach erneut.
Fehlt ein Ziel, eine Auswahl oder der genaue Link, bleibt das Aktionsziel gespeichert
und CasaJev stellt genau eine Rückfrage; die nächste kurze Antwort setzt denselben
Auftrag fort. Senden, Veröffentlichen, Käufe, Löschen, Konto-/Sicherheitsänderungen,
CAPTCHAs und Geheimnisse bleiben ausgeschlossen. Bei Runden- und Gewinnzielen zählen
Start, Resume oder ein einzelner Spielzug nicht als Abschluss; erforderlich ist ein
sichtbarer Ergebnisbeleg. Die lokale Makrosteuerung ist kein allgemeines
60-FPS-Bildverständnis.

Der erste native Desktop-Lesepfad kann per Chat Dateinamen in Desktop, Dokumente und
Downloads suchen, laufende Prozesse ohne deren potenziell geheime Kommandozeilenargumente
anzeigen, installierte Apps auflisten und die aktive App erkennen. Dateiinhalte,
versteckte Ordner, Löschen, Prozess-Beenden, Bildschirmaufnahmen anderer Apps und globale
Maus-/Tastatursteuerung sind noch nicht freigegeben. Diese zweite Kontrollstufe soll
später nur sichtbar, zeitlich begrenzt und an genau eine ausgewählte App gebunden sein.

„Google …“ startet jetzt einen sichtbaren, begrenzten Ablauf: Google öffnen, Jev einen
beobachteten Treffer auswählen lassen und die Quelle lesen. Freie Zusammenfassungen
formuliert weiterhin das Codex-Sprachmodell. Der Browser arbeitet standardmäßig im Hintergrund. Über **Browser** kannst du
jederzeit zuschauen; die Ansicht aktualisiert sich bei sichtbarem Tab bis zu zweimal
pro Sekunde. Es gibt keine künstlichen Pausen oder nachgespielten Mausbewegungen.
Browserzeit und gesamte Antwortzeit stehen unter der Antwort. Die Browserzeit bei
einer Suche enthält auch Jevs Trefferauswahl. Der zusätzliche Aufwand der Live-Ansicht
ist noch nicht separat vermessen.

Google kann eine CAPTCHA-Prüfung verlangen. Dann hält CasaJev an und zeigt die Seite
zur manuellen Übernahme; es umgeht die Prüfung nicht. Im Live-Test trat genau diese
Sperre auf. Die vollständige Google-Trefferauswahl ist deshalb bislang nur mit
kontrollierten Testdaten geprüft. Direktes Öffnen, Lesen und sichtbare Darstellung
wurden live geprüft. Bestellungen, Warenkörbe und autonome Formulare bleiben
absichtlich ausgeschlossen.

Aktuell unterstützt: CSV, JSON, Zahlenlisten und andere JSON-kompatible Eingaben als
reine Datentransformationen. Python erzeugt das Ergebnis; die Quelldateien bleiben
unverändert. Freie Gesprächsantworten und Zusammenfassungen entstehen über eine von Jev gewählte
Sprachmodellroute. Aktuelle Wissensfragen und ausdrückliche Rechercheaufträge erhalten
jetzt eine Live-Websuche mit Quellenlinks. Webseiten können durch eine Chatnachricht
geöffnet, gelesen und zusammengefasst werden, einschließlich der gerade sichtbaren
Browserseite. Vor jeder Entscheidung verdichtet deterministischer Code Ziel,
Constraints, Objekte, die letzten fünf Beobachtungen und den endlichen Aktionsraum.
Jev beziehungsweise eine andere `DecisionPolicy` sieht diesen kleinen Zustand statt
des gesamten Rohzustands. Bei Unsicherheit routet ein risikobasiertes Confidence-Gate
in eine begrenzte Eskalation. Eine unsichere gültige Werkzeugentscheidung kann pro
Aufgabe einmal vom GPT-Supervisor überprüft werden. Er darf nur eine bereits angebotene
Aktion auswählen und weder ausführen noch neue Rechte oder Aktionen erzeugen;
ungültige Modellantworten bleiben gesperrt und bestehende Ausführungsprüfungen gelten weiter. Übersetzen, Schreiben, Erklären
und Zusammenfassen laufen ebenfalls über diesen Weg. Zahlen in normalem Text oder Textanhängen können aufbereitet werden. Ein konservativer Abgleich kontrolliert Zahlenwerte, Vorzeichen, Duplikate und bei Zahlenlisten die Reihenfolge; Mehrdeutigkeit führt zur Rückfrage. Nichtnumerische Bedeutung und die allgemeine Korrektheit der Aufbereitung sind damit nicht bewiesen.

E-Mail-Versand, Scheduling, OAuth-Integrationen, autonome Formulareingaben und sonstige
externe Schreibzugriffe sind weiterhin nicht implementiert. Es werden keine solchen
Aktionen behauptet. Die Webrecherche ist ein hybrider Jev/Codex-Lauf, keine eigenständige
Textgenerierung oder Websuche durch das Jev-Modell.

## Verwaltung und Wiederaufnahme

- **Werkzeuge:** Verträge und Prüfnachweise ansehen, erneut prüfen, deaktivieren und mit erneuter Prüfung aktivieren. Absichtlich deaktivierte Standardwerkzeuge bleiben beim Neustart deaktiviert.
- **Skills:** eigene Textanleitungen für GPT-Aufbereitung und Builder, mit Aktivierung und Bearbeitung. Diese sind keine ausführbaren Jev-Capabilities.
- **Accounts:** TypeSafe-Schlüssel lokal hinterlegen, TypeSafe-Verbindung und vorhandene Codex-CLI-Anmeldung prüfen; Browser-Sitzung löschen.
- **MCP:** vertrauenswürdige lokale stdio-Server konfigurieren, Katalog abrufen, einzelne lesende Werkzeuge auswählen. Unterstützt Text/JSON, keine OAuth-Einrichtung, HTTP-MCP, Sampling oder externen Schreibabläufe. Die Programme laufen mit Benutzerrechten; „lesend“ ist eine bewusste Freigabe des Nutzers, keine technische Sandbox-Garantie des fremden Servers. Umgebungswerte werden nicht über die Verwaltungs-API zurückgegeben. Geheimnisse gehören in die Umgebungsfelder, nicht in Kommandoargumente.
- **Einstellungen:** getrennte Jev-/Laya-Auswahl für allgemeine und Echtzeitentscheidungen, Chat-/Builder-Modelle, Auftragsbudgets, begrenzte Fehlerwiederholungen, Speicherung der Browser-Sitzung.
- **Anhalten / Fortsetzen:** kontrollierter Abbruch lokaler Worker und Codex-Prozesse, gespeicherter Aufgabenstand. Ein laufender Jev-HTTP-Aufruf oder Browserzugriff kann noch bis zu seinem Zeitlimit benötigen. Verbraucht gebliebene Budgets werden nicht zurückgesetzt.
- **Export:** Chat und JSON-Ergebnis lokal herunterladen.

Temporäre Worker-Startfehler erhalten eine eigene Fehlerklasse und dürfen nach einer Jev-Entscheidung begrenzt wiederholt werden. Fehlerhafter Code, ungültige Ergebnisse und Zeitüberschreitungen werden nicht pauschal erneut ausgeführt. MCP-Aufrufe erhalten keine automatische Wiederholung.

Die vorhandene SQLite-Datenbank enthält zusätzlich Skills, Verbindungsdefinitionen, Chat-Metadaten und einen FTS5-Suchindex. Zugangsdaten und Browserzustand bleiben im privaten lokalen Zustandsverzeichnis. Ein Datenbankinhalt wird dadurch nicht zu trainiertem Modellwissen. Schema-Erweiterungen erfolgen beim Start ohne Löschen bestehender Chats oder Werkzeuge.

Nur die allgemeinen Backoff-Helfer wurden aus Hermes übernommen; Lizenz und Herkunft stehen in `THIRD_PARTY_NOTICES.md`. CasaJev behält seinen eigenen Jev-Loop, seine geprüfte Werkzeugbibliothek und die leichte Oberfläche. Prüfung dieser Version: `HARNESS-0.4.md`.

## Installation auf macOS, Windows und Linux

Voraussetzungen auf allen Systemen: `uv` und für GPT-Funktionen die Codex CLI mit
Anmeldung. Das Steuerprogramm benötigt Python >=3.11; `uv` verwaltet die Runtime.
macOS benötigt zusätzlich die Command Line Tools. Windows und Linux benötigen Docker,
weil dynamisch gebaute Werkzeuge niemals direkt im Host-Python ausgeführt werden.

```sh
uv sync --python 3.11 --extra local --extra test
uv run playwright install chromium
uv run casajev serve
```

Die Python-Pakete und die Oberfläche sind plattformneutral. Version 0.5.1 wurde auf
macOS vollständig ausgeführt. Unter Windows liefen gezielte Browser- und Desktop-Tests;
ein vollständiger Ende-zu-Ende-Test steht noch aus, weil die Docker Engine auf dem
Test-PC nicht lief. Linux wurde noch nicht auf einem realen Host Ende-zu-Ende geprüft.

Für den allgemeinen Standardpfad wird ein TypeSafe-Schlüssel benötigt. Der lokale
Laya-Pfad ist für eine konkret evaluierte Anwendung ausdrücklich wählbar:

```sh
uv run casajev --policy laya serve
```

Alternativ eine lokale Datei mit `TYPESAFE_API_KEY=...` verwenden:

```sh
uv run casajev --credentials-file /absoluter/pfad/typesafe.env serve
```

Schlüssel nicht in Aufgaben oder Daten einfügen. Beim Jev-Modus gehen
Aufgaben und Eingabedaten an TypeSafe; bei fehlender Fähigkeit und bei freien Gesprächsantworten
bekommt Codex den relevanten Gesprächs-/Aufgaben-Kontext.
Die lokalen Ereignisprotokolle enthalten diesen Kontext und Ergebnisse. Nur synthetische
Daten wurden für die mitgelieferte Evidenz benutzt. Der Dienst bindet nur an Loopback,
prüft Host/Origin und akzeptiert keine fremden Websites als Schreibclients.

## Befehle

Alle Befehle im Projektverzeichnis ausführen. `--home` und `--credentials-file` stehen
vor dem Unterbefehl. `.casajev` ist standardmäßig das lokale Zustandsverzeichnis.

```sh
uv run casajev doctor
uv run casajev run examples/csv.json
uv run casajev run examples/category-totals.json
uv run casajev tasks
uv run casajev tools
uv run casajev workflows
uv run casajev inspect AUFGABEN_ID
uv run casajev resume AUFGABEN_ID --clarification 'Genauere Beschreibung'
uv run casajev resume AUFGABEN_ID --objects weitere-objekte.json
uv run casajev --home .casajev-demo demo --repeat 2
uv run --extra test pytest -q
```

## Echtzeit-Anwendungen

`casajev.realtime.RealtimeController` ist der direkte Pfad für Sensor-, UI- und
Automationsereignisse. Er hält nur den neuesten eingereichten Zustand, verwirft
Rückstau, lehnt veraltete Beobachtungen ab und ersetzt eine zu spät eintreffende oder
zu unsichere Modellentscheidung durch eine vorher festgelegte sichere Aktion. Die
ausführende Anwendung bleibt für Berechtigungen, Aktuatorgrenzen und Not-Aus zuständig.

```python
from casajev.jev import Jev
from casajev.realtime import from_settings

loop = from_settings('.casajev', jev=Jev('typesafe-key'), safe_action='stop')
# Falls in den Einstellungen Laya gewählt wurde: vor dem zeitkritischen Abschnitt laden.
if hasattr(loop.controller.policy, 'warmup'):
    loop.controller.policy.warmup()
result = loop.step(
    observation={'goal':'Temperatur begrenzen', 'sensor':{'temperature_c':82}},
    actions={'observe':{'description':'Neu messen','risk':'read'},
             'cool':{'description':'Freigegebene Kühlung','risk':'compute'},
             'stop':{'description':'Sicher anhalten','risk':'passive'}},
    instructions='Wähle die nächste sichere Aktion.')
```

Das ist ein Soft-Realtime-Controller, keine zertifizierte Sicherheitssteuerung. Auf
dem getesteten Intel i7 mit 16 GB RAM erreichte der Laya-Prozess maximal etwa 2,37 GB
Resident Memory. Harte Millisekunden-Regelkreise, Medizin-, Fahrzeug- und andere
sicherheitskritische Aktuatoren gehören nicht in diesen Modellpfad.

`demo` verwendet einen ausdrücklich simulierten Entscheider, keine Jev-API.
Für Demo und Live getrennte Zustandsverzeichnisse verwenden. `run --no-templates`
überspringt Vorlagen für diesen Lauf; Wiederverwendung registrierter Werkzeuge bleibt
möglich. `inspect` zeigt den tatsächlichen Verlauf einschließlich Jev-Antworten,
Modellkennung, Laufzeiten und Token-Nutzung.

## Jev ohne GPT prüfen

`run --jev-only` verwendet ausschließlich bereits registrierte Werkzeuge. GPT-Planung,
GPT-Entscheidungshilfe, Vorlagenbau und neuer Werkzeugcode sind in diesem Modus gesperrt.
Die Ausführungspolitik wird mit der Aufgabe gespeichert und gilt auch beim Wiederaufnehmen.
Fehlende Werkzeuge werden als `needs_capability` gemeldet; Werkzeugfehler halten an.
Der normale Chat bleibt weiterhin hybrid.

```sh
uv run casajev --home .casajev run aufgabe.json --jev-only
```

Der getrennte Live-Vergleich mit begrenzter GPT-Unterstützung lässt sich reproduzieren:

```sh
uv run python -m casajev.autonomy_eval --output /pfad/leerer-ausgabeordner --credentials-file /pfad/typesafe.env --repeats 2
```

Er verwendet isolierte Register mit vier vorher geprüften Werkzeugen und verändert keine
bestehenden Chats. Sämtliche Modellaufrufe einschließlich GPT-Auftragsaufbereitung werden
gezählt. [Ergebnisse und Grenzen des Autonomietests](AUTONOMIE-TEST.md).

## Ablauf

1. **Beobachten und kompilieren:** Deterministischer Code reduziert den gespeicherten
   Missionszustand auf Ziel, Constraints, kompakte Objekte, fünf Beobachtungen und
   die jetzt verfügbaren Aktionen. Große Werte werden begrenzt und gehasht.
2. **Auswahl und Gate:** Die konfigurierbare `DecisionPolicy` bewertet nur den endlichen
   Aktionsraum. Tool und Eingabe bleiben fest gebunden. Das Gate verlangt je nach
   Risiko 0,55 (passiv), 0,65 (lesen/rechnen), 0,80 (submit/write), 0,95
   (destruktiv) oder 0,99 (kritisch).
3. **Eskalation:** Niedrige Confidence oder keine gültige Aktion beendet den Auftrag
   nicht pauschal. Im Datenloop darf ein enger GPT-Supervisor einmal eine vorhandene
   Aktion wählen; in der Browsersuche bleibt das System auf der Trefferliste.
4. **Wunsch:** `need_capability` erhält das Originalziel und optionale Hinweise auf
   Operation, Objekt und Ergebnisart. Unsichere Hinweise löschen den Wunsch nicht.
   `other` lässt neue Begriffe zu.
5. **Spezifikation:** Erst kommen passende geprüfte Vorlagen. Jev wählt oder verwirft.
   Danach kann Codex neue Verträge vorschlagen. Ablehnung führt zu begrenzter Revision,
   anhaltende Unklarheit zu einer Rückfrage.
6. **Bau:** Eine passende Vorlage benötigt kein Coding-Modell. Neue Implementierungen
   kommen über `codex exec` als strukturierter Quelltext zurück. Codex erhält keine
   freigegebene Ausführungsmöglichkeit für das Werkzeug und benötigt keine Shell-Tools.
7. **Prüfung:** Schema, erlaubte Imports/Quelltextstruktur, exakte Vertragsbeispiele,
   Ressourcenlimits und Betriebssystembeschränkungen. Fehlgeschlagene Prüfungen führen
   zu einer begrenzten Reparatur; ungeprüfter Code wird nicht registriert.
8. **Wiederaufnahme:** Jev sieht das neue Werkzeug im Register, wählt es aus und bekommt
   dessen tatsächliches Ergebnis als neues Objekt. Weitere Werkzeuge können dieses
   Ergebnis verwenden. Auftragsabschluss benötigt mindestens eine beobachtete Ausgabe.
9. **Ergebnisprüfung:** Ein optionales `acceptance.expected` bleibt lokal und wird weder
   Jev noch dem Builder übermittelt. Ohne diesen Sollwert wird ausdrücklich nur
   Vertragsprüfung plus Jev-Abschlussentscheidung bescheinigt.

## Effizienz und Modelle

Reihenfolge: **bestehendes Werkzeug → Kombination vorhandener Werkzeuge → Vorlage →
Codex → konfiguriertes Eskalationsmodell bei Reparatur**. Kombination erfolgt über
mehrere Entscheidungen und Ergebnisreferenzen, nicht über einen DAG-Optimierer.

- Vier mitgelieferte Vorlagen: exakte CSV-Dubletten, Zahlen sortieren, Zahlen summieren und strikt positive Zahlen filtern.
- Inhaltsbasierte Vertrags- und Implementierungs-IDs; gleiche exakte Verträge erhalten
  keine gleichzeitig aktiven Duplikate. Semantisch ähnlich formulierte Verträge werden
  nicht zuverlässig als identisch erkannt.
- Ein Worker verhindert konkurrierende Builds auf demselben Register.
- Standardbudgets je Aufgabe: 18 Phasen/Schritte, 24 Jev-Aufrufe, 6 Codex-Aufrufe,
  2 Bauversuche einschließlich Reparaturen, 600 Sekunden zwischen Phasen geprüft.
  Jev-Anfragen haben 30 s Timeout, Codex 150 s, Werkzeugaufrufe 8 s und 3 s CPU-Limit.
  Ein laufender Provideraufruf kann das Gesamtzeitbudget bis zu seinem Timeout überziehen.
- Eingabe-/Ausgabegrößen sind begrenzt; Prozessgruppen werden nach Abschluss/Timeout
  beendet. API-Fehler werden nicht endlos erneut angefragt.
- Die risikobasierten Schwellen sind Entwicklungsheuristiken, keine kalibrierten
  Wahrscheinlichkeiten oder Sicherheitsgarantien. Destruktive und kritische Aktionen
  sind weiterhin nicht implementiert; ihre Schwellen bereiten nur die Schnittstelle vor.

Das Builder-Modell kann über `CASAJEV_BUILDER_MODEL` gesetzt werden. Optional
`CASAJEV_ESCALATION_MODEL` für Reparaturen. Ohne Einstellung verwendet Codex seinen
CLI-Standard bei direkter Verwendung der Builder-Klasse. Die Anwendung nutzt jetzt
standardmäßig Terra/Medium für Werkzeugbau und Sol/Medium für Reparatur-Eskalation.
Gesprächsplanung und Recherche nutzen Terra/Low (`CASAJEV_CHAT_MODEL` ist konfigurierbar).
Dies ist ein einstellbarer Entwicklungsstandard, kein nachgewiesen optimaler Modellmix.
Der gemessene Vergleich betrifft die Nutzung vorhandener Werkzeuge; siehe [VERGLEICH.md](VERGLEICH.md).
Jev ist für reproduzierbare Messungen auf `jev-1.13.0` festgelegt.

## Nachweise und Grenzen

Siehe [TESTERGEBNIS.md](TESTERGEBNIS.md) und `evidence/`. Die Tests prüfen unter anderem
Neustart, Wiederverwendung, Komposition, Reparatur, unerlaubte Rechte, korrumpierte
Werkzeuge, veralteten Zustand, Timeout sowie OS-Sperren für Datei-/Netzzugriffe.

Die Vertragsbeispiele eines neuen Werkzeugs kommen zunächst vom Builder. Der
separate Runner führt sie unabhängig aus, macht sie aber nicht zu unabhängigen
inhaltlichen Testfällen. Deshalb sind die separat hinterlegten Sollwerte wichtig.
Einige erfolgreiche synthetische Aufgaben beweisen keine allgemeine Zuverlässigkeit.

Der macOS-Worker blockiert Netzwerk, Schreiben, Lesen aus Benutzer-/Temp-Verzeichnissen,
Kindprozesse, fremde Executables, Signale und Mach-Service-Lookups. Er bekommt keinen
API-Schlüssel. Betriebssystem-/Frameworkdateien bleiben teilweise lesbar. Die
Quelltextprüfung ist eine zusätzliche Einschränkung, keine eigenständige Sandbox.
Das ist ein lokaler Prototyp, keine auditierte Plattform für feindlichen Fremdcode oder
mehrere Nutzer. Ein container-/VM-basierter Worker ist der nächste Portabilitätsschritt.

## Herkunft

[IDEEN.md](docs/IDEEN.md) ordnet die aus der vorherigen Unterhaltung übernommenen Ideen
und die noch offenen Erweiterungen ein. Jev erweitert hier seinen Werkzeugbestand,
nicht seine Modellgewichte.

Am 20.09.2026 abgeglichene Primärquellen:

- [TypeSafe API](https://docs.typesafe.ai/api) — Zustand, Choice-Fragen, Antworten.
- [TypeSafe Function Calling](https://docs.typesafe.ai/cookbooks/function_calling) —
  Code führt aus, Jev wählt strukturierte Optionen.
- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) —
  `exec`, JSON-Schema-Ausgaben und vorhandene CLI-Anmeldung.
- [Playwright Browser API](https://playwright.dev/python/docs/api/class-page) —
  lokale Chromium-Sitzung, Darstellung und Interaktionen.
- [Foreman](https://github.com/thruwire/foreman) — Referenz für begrenzte Läufe,
  Ereignisprotokolle und Wiederaufnahme; kein Foreman-Quellcode übernommen.


## Ablaufgraph und Graphify

`casajev/workflows.py` baut einen gerichteten Graphen aus dem aktuellen geprüften
Werkzeugregister und abgeschlossenen Ausführungen. Werkzeuge, Datenarten und vergangene
Abläufe sind Knoten. Rechte, Quelltext- und Vertragshashes bleiben maßgeblich.
Eine passende Datenart erzeugt nur einen **vermuteten** Verbindungsvorschlag (`INFERRED`).
Eine echte Ausgabe-zu-Eingabe-Verbindung aus einem abgeschlossenen Lauf wird als
beobachteter Datenfluss (`EXTRACTED`) gespeichert, samt Aufgabenreferenz.

Jev erhält vor jeder Werkzeugentscheidung eine kleine Auswahl möglicher Kombinationen
und ähnlicher abgeschlossener Abläufe. Das ist zunächst eine begrenzte, lexikalische
Suche und ein Typgraph, kein trainierter Planer und kein beliebiger Workflow-Compiler.
Das Harness prüft weiterhin jede Werkzeugwahl, jeden Eingabewert und jede Ausgabe.
Gesperrte oder geänderte Werkzeuge werden aus den Graphhinweisen entfernt.
Die Prüfung eines erfolgreichen Laufs wird mitgespeichert; eine Jev-Abschlussentscheidung
ist nicht mit einem unabhängigen Sollvergleich gleichzusetzen.

Nach erfolgreicher Ausführung wird `.casajev/graphify-out/graph.json` aktualisiert;
`uv run casajev workflows` exportiert den aktuellen Stand auch manuell. Das Format
wurde mit der installierten Graphify-CLI per `graphify query` geprüft. Die
Laufzeit arbeitet direkt mit dem kleinen Graphen und benötigt keinen zusätzlichen
Graphify-Modellaufruf für jeden Schritt. Graphify dient hier der Navigation und
Inspektion. Ausführungsbelege bleiben die Originaleinträge in SQLite.

**Kein nachgewiesener Graph-Vorteil im kleinen Pilot:** Dieselben Aufgaben wurden auch
mit deaktivierten Graphhinweisen ausgeführt. Größere Register, längere Ketten und
fremde Aufgaben stehen noch aus. Der Graph ist keine automatische Autorisierung.

## Direkt im Chat ausprobieren

- „Wer ist aktuell Bundeskanzler? Bitte mit offizieller Quelle.“
- „Lies https://example.com und fasse die Seite in einem Satz zusammen.“
- „Übersetze ins Englische: Der Termin wurde auf Freitag verschoben.“
- „Schreib eine kurze freundliche Terminabsage.“
- „Filtere positive Zahlen und summiere sie: [-4, 8, 0, 3, -2].“
- „Berechne 19 Prozent von 249.“

Quellenlinks öffnen sich im integrierten Browser. Der Chat zeigt einen kurzen
Arbeitsstatus und die gemessene Bearbeitungsdauer. Die Oberfläche bleibt ein einzelnes
Eingabefeld. Anhänge sind weiterhin Text/CSV/JSON, keine allgemeine PDF-/Office-Verarbeitung.
