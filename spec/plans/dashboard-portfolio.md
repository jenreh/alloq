# Umsetzungsplan: Übersicht als Portfolio (Variante C)

Grundlage ist der Entwurf C „Portfolio“ im Design-Artefakt
https://claude.ai/artifact/7YFv9dz5VcSEzN4nqaioax. Die Übersicht (`/`) zeigt danach vier
Karten: Zeit und Fortschritt je Projekt, offene Risiken als Matrix, den kritischen
Ressourcenpfad und die Kapazität je Rolle. Oben in der Werkzeugleiste wählt man den
Bereich: ganze Abteilung oder direkt unterstellt.

## Ziel

Die Abteilungsleitung sieht auf einen Blick, wie die Projekte stehen, ob die Kapazität
reicht, welche Risiken drücken und an welcher Rolle oder Person das Enddatum hängt.
Jede Zahl kommt aus vorhandenen Daten. Es gibt keine neuen Tabellen und keine Migration.

## Begriffe und Regeln

- **Bereich „Ganze Abteilung“:** alle Personen und alle Projekte.
- **Bereich „Direkt unterstellt“:** Personen mit `manager_id` = Mitarbeiter der
  angemeldeten Person (gefunden über die E-Mail). Projekte, in deren `owners` diese
  Person steht. Gibt es kein Mitarbeiterprofil zur Anmeldung, ist der Bereich leer und
  die Seite sagt das.
- **Zeitraum:** 13 Wochen ab dem Montag der aktuellen Woche. Für den Puffer wird bis zu
  52 Wochen vorausgerechnet.
- **Verfügbar je Rolle und Woche:** Summe der verfügbaren Tage der Personen mit der
  Rolle (Abwesenheit, Feiertage und interne Stunden abgezogen, wie im Heatmap-Service).
  Zeit, die eine Person in einer anderen Rolle gebucht hat, zählt nicht mit.
- **Geplant je Rolle und Woche:** Summe der `CapacityAllocation` der Personen im Bereich,
  über alle nicht abgeschlossenen Projekte.
- **Freie Kapazität:** verfügbar minus geplant, **ohne** Kappung bei 0. Ein negativer
  Wert heißt: die Rolle ist überbucht.
- **Restbedarf je Projekt und Rolle:** `RequiredCapacity.person_days` minus die
  Personentage, die vor dieser Woche schon gebucht waren.
- **Lücke:** Restbedarf minus die ab dieser Woche geplanten Personentage, mindestens 0.
- **Bedarf je Rolle im Zeitraum:** geplant plus der Anteil der Lücke, der auf die
  13 Wochen fällt. Die Lücke wird dafür gleichmäßig auf die Restwochen des Projekts
  verteilt.
- **Puffer in Wochen:** Für jede Rolle eines Projekts wird ab dieser Woche gezählt:
  erst die geplanten Tage, dann freie Kapazität der Rolle. Die Woche, in der der
  Restbedarf erreicht ist, heißt Deckungswoche. Puffer = Endwoche minus Deckungswoche.
  Die Projekte bekommen freie Kapazität nach Enddatum, das früheste zuerst. Ein Projekt
  hat den kleinsten Puffer seiner Rollen. Ohne erfassten Bedarf gibt es keinen Puffer.
  Eine Rolle ohne Restbedarf kann das Projekt nicht verzögern: ihr Puffer ist
  mindestens 0, der Grund heißt „Bedarf erfüllt“.
- **Schwächstes Glied:** die Rolle mit dem kleinsten Puffer. Der Grund ist der erste
  zutreffende in dieser Reihenfolge: niemand eingeplant, Rolle überbucht, einzige Person
  ist abwesend, Träger über 100 % bei Projektende in höchstens 8 Wochen, nur eine
  Person trägt die Rolle, Lücke ohne Plan, alles gedeckt.
- **Farbe der Blase:** EAC zu Budget wie `_classify_overrun`: im Budget, bis 10 % über,
  mehr als 10 % über. Ohne EAC grau. Puffer unter 0 bekommt einen gestrichelten Ring.
- **Risikomatrix:** offene Risiken (`open`) der Projekte im Bereich, gezählt je
  Wahrscheinlichkeit und Auswirkung (beide 1 bis 5). Schwere wie bisher: bis 4 niedrig,
  bis 15 mittel, darüber hoch.

## Aufbau im Code

| Teil | Datei | Inhalt |
| --- | --- | --- |
| Lesemodelle | `alloq_dashboard/models.py` | `PortfolioKpi` und Teilmodelle |
| Eingaben | `services/portfolio_inputs.py` | Datenklassen, Laden aus der Datenbank, Bereichsfilter |
| Ressourcenpfad | `services/resource_path.py` | Verfügbar, geplant, frei, Lücke, Puffer, schwächstes Glied (reine Funktionen) |
| Portfolio | `services/portfolio.py` | Blasen, Risikomatrix, Rollen, Zusammenbau, `load_portfolio` |
| Zustand | `states/portfolio_state.py` | Daten, Laden, Bereich, Auswahl für den Drawer |
| Karten | `components/portfolio_*.py` | vier Karten, Drawer, Raster |
| Seite | `pages.py`, `components/dashboard_grid.py` | Bereich in der Werkzeugleiste, Raster statt der zwei alten Karten |

`aggregation.py` hat schon mehr als 1000 Zeilen. Neues kommt deshalb in eigene Module.
Alle Handler im neuen Zustand tragen `@requires_admin`.

## Schritte

1. Tests für die reinen Funktionen schreiben: Bereichsfilter, Lücke, Überbuchung ohne
   Kappung, Puffer (gedeckt, verspätet, nicht gedeckt, ohne Bedarf), schwächstes Glied
   mit jedem Grund, Risikomatrix, Blasen.
2. Modelle und Module wie oben bauen, bis die Tests grün sind.
3. Zustand mit Tests: Laden, Fehler, Bereichswechsel, Drawer öffnen und schließen.
4. Karten bauen: Blasen als absolut gesetzte Elemente (keine neue Chart-Bibliothek),
   Matrix als Raster, Ketten als Zeilen, Rollen als Balken mit Bedarfsstrich.
   Laden zeigt Platzhalter, leere Zustände zeigen einen Satz.
5. Drawer: Klick auf Blase oder Kette zeigt das Projekt mit Rollen, Lücke, Puffer und
   Grund. Klick auf ein Matrixfeld zeigt die Risiken darin.
   Klick auf die Rolle zeigt je Woche verfügbar, geplant und frei (frei auch negativ),
   die Personen mit der Rolle und die Projekte mit Lücke in dieser Rolle. Klick auf die
   Person zeigt die Auslastung je Woche, die Abwesenheiten im Zeitraum und die Projekte
   und Rollen, auf die sie gebucht ist. Die Drawer verlinken untereinander. Die Daten
   kommen fertig berechnet mit `PortfolioKpi` (`role_details`, `person_details`).
6. Seite umstellen, Render-Tests anpassen.
7. `task format`, `task lint`, `task typecheck`, `task test`; Seite lokal ansehen.

## Nicht in diesem Schritt

- Varianten A und B.
- Ein Filter nach dem neuen Feld `department_id`. Der Bereich nutzt wie vereinbart
  `manager_id` und `owners`.
