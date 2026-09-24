# Wiederkehrender CSV-Ablauf: synthetischer Vorlauf

Fünf Wochenfälle liegen in `evidence/weekly-csv-20260924/cases.json`. Sie prüfen
Wiederverwendung bei neuen Daten, einen geänderten Dublettenbegriff, Filtern →
Gruppieren → Summieren und einen beschädigten Export. Die erwarteten Ergebnisse
werden nicht an CasaJev oder den Bauagenten übergeben.

`casajev.weekly_csv_eval` führt die Fälle der Reihe nach mit drei Varianten aus:

1. Ein vorab geschriebenes festes Skript. Seine Entwicklungszeit wird nicht gemessen.
2. CasaJev mit einem über die Wochen persistenten Register, anfangs nur mit dem
   geprüften Werkzeug für exakte CSV-Dubletten.
3. Derselbe Harness mit Jev-Entscheidungen und GPT-Werkzeugbau, aber einem neuen
   leeren Register für jede Woche.

Beide Agenten haben dieselben Schritt-, Bau-, Aufruf- und Zeitlimits. Der Lauf
schreibt Fälle und Protokoll vor dem ersten Provider-Aufruf in ein leeres
Ausgabeverzeichnis. Danach speichert er vollständige Ereignisse und Ergebnisse.
Das ursprüngliche Protokoll bleibt erhalten, auch wenn eine spätere Auswertung
oder ein Code-Fix nötig wird.

```sh
uv run python -m casajev.weekly_csv_eval \
  --output /pfad/zu/neuem-leeren-verzeichnis \
  --credentials-file /pfad/zu/typesafe.env
```

Der erste Vorlauf vom 24.09.2026 zeigte, dass das ursprüngliche Kriterium für
beschädigte Eingaben zu locker war: Ein Ende am Bauaufruf-Limit wurde als
Anhalten gezählt. Die nunmehrige Auswertung verlangt `invalid_input` ohne
Ergebnis. Das Harness prüft die CSV-Form deshalb vor der Werkzeugausführung;
ein Datenfehler löst keine Werkzeugreparatur mehr aus. Diese Änderung gehört
**nicht** zum ursprünglichen Lauf und muss separat überprüft werden.

Die Daten sind synthetisch. Ein belastbarer Vergleich braucht anschließend
anonymisierte echte Wochenexporte mit vorab festgelegten Regeln und unabhängig
bestimmten Sollwerten. Zeiten des festen Skripts enthalten nur die Ausführung,
keine Skriptentwicklung; ein vollständiger Kostenvergleich ist dadurch offen.
