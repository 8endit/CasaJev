# CasaJev 0.5 – lokaler Soft-Realtime-Pfad

Stand: 21. September 2026.

## Ergebnis

CasaJev besitzt jetzt eine echte `DecisionPolicy`-Implementierung für Laya 0.3.4,
ohne den bewährten Jev-Pfad zu entfernen. Der Checkpoint wird revisionsfest geladen,
einmal vorgewärmt und liefert nur eine validierte Auswahl aus einem endlichen
Aktionsraum. Mehr als 20 Aktionen werden höchstens zweistufig gruppiert; oberhalb von
400 Aktionen hält der Provider an.

Der allgemeine Harness bleibt standardmäßig bei Jev. Der eingefrorene Acht-Fall-Test
zeigte für Laya nur 1/8 richtige Auswahlentscheidungen. Ein ungeprüfter Standardwechsel
wäre daher eine Regression. Laya ist als expliziter lokaler Provider für eine eng
begrenzte Anwendung verfügbar, nachdem deren eigener Holdout-Test bestanden wurde.

## Echtzeit-Invarianten

- Das Modell sieht einen deterministisch verdichteten Zustand und nur angebotene Aktionen.
- Die Queue hält genau den neuesten Zustand; ältere Frames werden bei Rückstau verworfen.
- Eine veraltete Beobachtung wird nicht ausgewertet.
- Eine nach der Deadline eintreffende Auswahl wird nie nachträglich ausgeführt.
- Ungültige oder zu unsichere Ausgaben werden durch die konfigurierte sichere Aktion ersetzt.
- GPT, Werkzeugbau, MCP und Webzugriffe liegen nicht im Echtzeitpfad.

Dies ist Soft-Realtime. Die auf dem Intel-Testgerät gemessenen rund 201 ms gelten nur
für den kleinen Drei-Aktionen-Fall. Die Anwendung muss Aktuatorgrenzen, Freigaben und
Not-Aus weiterhin deterministisch außerhalb des Modells erzwingen.

## Veröffentlichung und Sicherheit

- Apache-2.0-Projektlizenz, Drittanbieterhinweis, Security Policy und Contribution Guide.
- Python 3.11 sowie kompatible NumPy-, Transformers- und Torch-Versionen sind festgelegt.
- Laya-Modellrevision ist festgelegt; der Modellcache wird nicht veröffentlicht.
- Private SQLite-, Arbeits- und macOS-Dateien sind ignoriert.
- Der öffentliche Browser blockiert standardmäßig Loopback, private, link-local,
  reservierte und andere nicht-global routbare Ziele vor der Navigation und in jeder
  Browser-Anfrage. Ein expliziter privater Modus existiert nur für lokale Einbettungstests.

## Verifikation

Die vollständige Suite umfasst 106 Tests. Zusätzlich wurden der reale lokale
Laya-Checkpoint, Wheel-/sdist-Inhalte, der laufende Loopback-Server und die unveränderten
Zähler der bestehenden Zustandsdaten geprüft. Die synthetischen Modelltests sind keine
Behauptung über allgemeine Autonomie oder reale Aufgabenerfüllung.
