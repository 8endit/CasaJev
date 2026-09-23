# CasaJev 0.4 – hierarchischer, begrenzter Controller

Stand: 21. September 2026. Version 0.4 behält Werkzeugregister, Sandbox,
Verträge, Browser, Chat, MCP und SQLite-Zustand aus 0.3. Der Umbau ersetzt weder
die Datenbank noch bestehende Werkzeuge und Chats.

## Umgesetzt

- `StateCompiler`: deterministische, begrenzte Missionssicht mit Ziel, Constraints,
  Objektsummaries, fünf letzten Beobachtungen und aktuellem Aktionsraum.
- `DecisionPolicy`: austauschbare Provider-Schnittstelle. `JevDecisionPolicy` ist der
  aktuelle Adapter; andere Policies können in `Harness(..., decision_policy=...)`
  eingesetzt werden, ohne Ausführung oder Verifikation zu ändern.
- `ConfidenceGate`: aktionsbezogene Schwellen für passive, lesende, rechnende,
  schreibende, destruktive und kritische Aktionen.
- `FastLoop`: wiederverwendbares `observe → compile → decide → gate → execute` mit
  Schrittbudget, Trace und expliziter Eskalationsroute.
- Der Daten-Harness persistiert Confidence, Schwelle, Risiko, Distribution,
  Akzeptanz und Eskalationsereignisse. Der GPT-Supervisor darf pro Auftrag einmal
  ausschließlich aus den bereits kompilierten Aktionen wählen.
- Chat-Routing und sichtbare Google-Trefferauswahl verwenden denselben Controller.
  Unsicherheit in der Browsersuche navigiert nicht, sondern lässt die Treffer sichtbar.

## Sicherheitsgrenzen

- Provider erzeugen keine ausführbaren Aktionen; der Harness erzeugt und bindet den
  Aktionsraum an konkrete Tool/Input-Paare.
- Eine Supervisor-Antwort führt nichts selbst aus und kann keine Berechtigung erfinden.
- Bestehende Vertrags-, Hash-, Schema-, Permission-, Sandbox- und Ergebnisprüfungen
  bleiben nach der Auswahl maßgeblich.
- Schreibende, destruktive und zahlungsbezogene Browseraktionen sind nicht freigeschaltet.
  Die hohen Schwellen sind vorbereitet, aber keine Behauptung solcher Fähigkeiten.
- Confidence-Werte sind nicht kalibriert. Ein hoher Wert ersetzt weder unabhängige
  Ergebnisprüfung noch Nutzerbestätigung.

## Prüfung

- Vor dem Refactor: 95 Tests bestanden.
- Nach dem Refactor: 99 Tests bestanden, darunter neue Tests für State-Bounding,
  risikobasierte Gates, bounded escalation und Policy-Austauschbarkeit.
- Zusätzlich bleiben die vorhandenen Tests für echte isolierte Worker, Browserzustand,
  SQLite-Neustart, MCP, Origin-Prüfung, Tool-Integrität und falschen Abschluss aktiv.

Dies ist ein sauber integrierter Controller-Refactor. Er ist noch kein Nachweis, dass
Jev bei realen Kundenaufgaben GPT oder einen festen Workflow übertrifft; dafür bleibt
der getrennte Holdout-Vergleich maßgeblich.
