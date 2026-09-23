# Laya-Eignungstest für CasaJev 0.5

Stand: 21. September 2026. Gerät: Intel Core i7-7820HQ, 16 GB RAM, CPU-Inferenz,
Python 3.11, Laya 0.3.4, mehrsprachiger Checkpoint auf Revision
`1c5edc17a7acd8701df6fc341c0d179f1c62c982`.

## Gemessen

- Kleiner Drei-Aktionen-Zustand, 12 warme Wiederholungen: 200,8 ms Median,
  206,1 ms P95, 191,2 ms Minimum.
- Erstes Laden inklusive Modellaufbau: 30,8 s im ersten Messlauf; 34,3 s beim
  anschließenden Adaptertest.
- Maximaler Resident Set Size: rund 2,37 GB.
- Eingefrorener synthetischer CasaJev-Routingtest mit acht deutschen Fällen und acht
  Aktionen: Laya 1/8 richtige Auswahl, Jev 8/8. Median pro Auswahl: Laya 3142,9 ms,
  Jev 697,5 ms.

## Schlussfolgerung

Laya ersetzt Jev nicht als allgemeinen CasaJev-Router. Die lokale Laufzeit passt in den
Arbeitsspeicher und ist bei sehr kleinen Aktionsräumen schnell genug für Soft-Realtime,
aber die ungeprüfte Zero-Shot-Auswahl ist für den allgemeinen Harness nicht zuverlässig.
Eine konkrete Echtzeit-Anwendung darf Laya erst nach einem eigenen eingefrorenen
Holdout-Test, einer passenden Konfidenzkalibrierung und einem sicheren Fallback aktivieren.

Dies ist kein allgemeiner Modellbenchmark: acht synthetische Routingfälle beweisen weder
Produktionsqualität noch Überlegenheit von Jev außerhalb dieses engen Tests.
