# Plan: macOS-App-Rahmen für alloq

Stand: 14.10.2026. Vorlage ist der Design-Prototyp
<https://claude.ai/artifact/Bq3xADjUF3DPw2eoVtKCnK> und der App-Rahmen aus
`vermoegen/portfolio/ui/layout.py` und `theme.py`.

## Stand der Umsetzung (14.10.2026)

| Phase | Stand |
| --- | --- |
| 1 Tokens und Theme | umgesetzt: `alloq_commons/theme.py`, alte `--alloq-*` als Aliase |
| 2 Rahmen, Seitenleiste, Toolbar | umgesetzt: `shell.py` (`app_page`), `toolbar.py`, `app/components/sidebar.py` |
| 3 Listen mit Inspektor | umgesetzt: `list_view.py`, Projekte und Team als Liste mit Inspektor |
| 4 Login im Splash-Stil | umgesetzt: `app/pages/login.py`; Splash mit Fortschrittsbalken folgt mit Phase 5 |
| 5 Desktop-App | offen, wartet auf die Entscheidung zu Risiko 1 |

Abweichungen vom Plan: Die Listenlogik steckt in Reflex-Mixins
(`ProjectListState`, `TeamListState`) statt in Substates, weil deren berechnete
Variablen sonst überall einen vollständigen State-Baum verlangen. `app_page`
nutzt `authenticated_page` von appkit mit eigenem Template; `auth.py` und
`page_header.py` sind entfernt. Die Suche in der Seitenleiste (⌘K) ist noch
nicht umgesetzt.

## Ziel

alloq bekommt den Rahmen einer nativen macOS-App: eine durchscheinende
Seitenleiste links, einen schwebenden weißen Inhaltsbereich rechts und eine
Toolbar oben in diesem Bereich. Derselbe Code läuft im Browser und als
Tauri-Desktop-App. Die Desktop-App bettet das Python-Backend ein wie vermoegen,
nutzt aber keine lokale Datenbank, sondern die zentrale Postgres-Datenbank. Der
Login sieht aus wie der Splash-Screen von vermoegen.

## Ausgangslage

- Jede Seite entsteht über `alloq_commons.components.auth.authenticated`. Das
  ruft `appkit_user.authentication.templates.authenticated` auf. Dort baut
  `_render_layout` den Rahmen: Navbar links, darunter ein scrollender Stack. Den
  Rahmen können wir nicht ändern, ohne appkit zu ändern.
- Die Navigation steckt in `app/components/navbar_collapsible.py` (773 Zeilen):
  eine Icon-Leiste plus ein aufklappbares Panel je Bereich.
- Jede Seite baut ihren Kopf selbst: eine eigene Toolbar oben rechts
  (`planning_toolbar`, `project_toolbar`, …) und `page_header` mit einem großen
  Titel (3rem). Beides wird im neuen Rahmen zur Fenster-Toolbar.
- Die Farben stehen in `assets/css/alloq-theme.css` (852 Zeilen) als
  `--alloq-*`-Variablen und umgefärbte Mantine-Paletten. Das Mantine-Theme steht
  in `app/app.py`.
- Die App läuft unter `frontend_path: /alloq`. Alle Zugangsdaten kommen als
  `secret:`-Werte aus dem Key Vault.

## Zielbild

Das Zielbild ist der Prototyp:

| Bereich | Inhalt |
| --- | --- |
| Seitenleiste (244px) | Zeile für die Fensterknöpfe, Logo und Mandant, Suche mit ⌘K, Abschnitte „Planung“ (Übersicht, Ressourcenplanung, Projekte, Team mit Zählern), „Meine Projekte“ (Farbpunkt, Anzahl offener Risiken), „Administration“ (nur für Admins), unten Benutzer mit Menü |
| Inhaltsbereich | weiße Fläche mit 14px Radius, 8px Abstand zum Fensterrand, Schatten wie in vermoegen |
| Toolbar (56px) | links Titel und eine Zeile Kontext, Mitte Segmented Control, rechts Suche, Icon-Buttons und höchstens ein blauer Hauptbutton |
| Listen | Projekte und Team als Tabelle mit Gruppen („Meine …“, „Weitere …“) und Inspektor rechts (320px) |
| Farben | neutrale helle Grautöne, Akzent Blau `#2E6BD6`, Status in gedämpftem Grün, Bernstein, Rot |
| Schrift | Systemschrift (SF Pro) wie in vermoegen |

## Entscheidungen

1. **Eigener Seitenrahmen statt appkit-Layout.** Neues Modul
   `alloq_commons/components/shell.py` mit einem Decorator `app_page(...)`. Er
   registriert die Seite mit `rx.page`, setzt `session_monitor()`, die
   Admin-Prüfung und den Ladezustand wie appkit, rendert aber unseren Rahmen.
   appkit bleibt unverändert. `authenticated` in `auth.py` ruft danach nur noch
   `app_page` auf, damit die Seitenfabriken kaum Änderungen brauchen.
2. **Tokens in Python, nicht in CSS-Dateien.** Neues Modul
   `alloq_commons/theme.py` nach dem Muster von vermoegen: `TOKENS` und
   `DARK_TOKENS` als Dicts, daraus `GLOBAL_CSS` mit `--aq-*`-Variablen,
   `token(name)` als Zugriff, `MANTINE_THEME` mit blauer Primärpalette und
   neutraler Dunkelpalette. Die alten `--alloq-*`-Variablen bleiben in einer
   Übergangsphase bestehen, bekommen aber die neuen Werte. So brechen
   bestehende Komponenten nicht, während wir sie umstellen.
3. **Eine Seitenleiste statt Leiste und Panel.** Neues Modul
   `app/components/sidebar.py` ersetzt `navbar_collapsible.py`. Einklappen per
   Button in der Titelzeile und ⌘\, Zustand im localStorage. Unter 768px wird
   die Seitenleiste zu einem Drawer.
4. **Toolbar als Slot.** `window_toolbar(title, subtitle, center, actions)` in
   `alloq_commons/components/toolbar.py` ersetzt `page_header` und die
   bisherigen Seiten-Toolbars. Die Seitenfabriken übergeben ihre Toolbar an
   `app_page(toolbar=...)`.
5. **Native Erkennung wie vermoegen.** Ein Head-Script setzt
   `html[data-native]`, wenn `window.__TAURI__` existiert. Nur dann wird der
   Fenstergrund transparent und die native Vibrancy sichtbar. Toolbar und
   Titelzeile tragen `data-tauri-drag-region`.

## Phasen

Jede Phase endet mit grünen Tests, `task format && task lint && task typecheck`
und lauffähiger Web-App. Phase 1 bis 4 ändern nichts an Tauri.

### Phase 1: Tokens und Theme

- `alloq_commons/theme.py` anlegen (Tokens hell und dunkel, `GLOBAL_CSS`,
  `MANTINE_THEME`, `HEAD_SCRIPTS`).
- `app/app.py`: `ALLOQ_THEME` durch `MANTINE_THEME` ersetzen, `GLOBAL_CSS` und
  `HEAD_SCRIPTS` einbinden, Roboto-Flex-Stylesheets entfernen.
- `alloq-theme.css`: Seitenverlauf `--alloq-app-bg` entfernen,
  `--alloq-*`-Werte auf die neuen Tokens zeigen lassen, umgefärbte
  Mantine-Paletten entfernen.
- Tests: `tests/test_theme.py` nach `vermoegen/tests/test_ui_pages.py`
  (Tokens in `GLOBAL_CSS`, Dunkelmodus, Primärpalette, native Regel).

### Phase 2: Rahmen, Seitenleiste, Toolbar

- `shell.py` mit `app_page` und `app_layout` (Seitenleiste, Inhaltsbereich,
  Toolbar-Slot, scrollender Inhalt).
- `sidebar.py` mit `SidebarState`: Zähler für Projekte und Team, „Meine
  Projekte“ des angemeldeten Benutzers mit Risikoanzahl, Admin-Abschnitt über
  `requires_admin`. Daten aus den vorhandenen Repositories, geladen einmal pro
  Sitzung und nach Änderungen.
- `toolbar.py` mit `window_toolbar`, `segmented`, `toolbar_search`.
- Alle Seiten umstellen: Dashboard, Ressourcenplanung, Projekte, Team,
  Benutzer, Rollen, Feiertage, Profil. `page_header` und `navbar_collapsible.py`
  danach löschen.
- Ressourcenplanung: Ansicht (Team, Projekte, Heatmap, Abwesenheiten) wandert
  als Segmented Control in die Toolbar, Filter in eine Scope-Leiste darunter.
- Tests: `SidebarState` (Zähler, eigene Projekte, Admin-Sicht), Routing der
  Einträge, aktive Markierung.

### Phase 3: Listen mit Inspektor

- Projekte und Team zeigen standardmäßig die Liste. Die Kachelansicht bleibt
  über den Umschalter in der Toolbar erreichbar.
- `project_table.py` und `employee_table.py` auf die neue Tabellenform bringen:
  Gruppen „Meine …“ und „Weitere …“, sortierbare Spalten, Auswahl einer Zeile.
- Neuer Inspektor je Liste (`project_inspector.py`, `employee_inspector.py`).
  Er zeigt Eckdaten, Budget und Fortschritt, Team, Risiken bzw. Auslastung der
  nächsten acht Wochen, Zuweisungen, Abwesenheiten. „Bearbeiten“ öffnet das
  vorhandene Modal.
- Filter als Segmented Control: Projekte (Alle, Meine, Aktiv, Geplant,
  Risiko), Team (Alle, Meine, Überlastet, Frei).
- Tests: Auswahl, Filter, Gruppierung in `ProjectState` und `TeamState`. Beide
  Dateien liegen schon bei 1454 bzw. 988 Zeilen. Die neue Logik kommt deshalb
  in eigene Substates (`ProjectListState`, `TeamListState`).

### Phase 4: Login im Stil des Splash-Screens

- Neue Login-Seite in `app/pages/login.py` statt `create_login_page` aus
  appkit: Verlaufshintergrund und App-Icon wie der Splash von vermoegen,
  darunter eine Karte mit E-Mail, Passwort, „Mit Microsoft anmelden“ und „Mit
  GitHub anmelden“. Die Anmeldelogik bleibt die von `LoginState`.
- Ablauf in der Desktop-App: Splash mit Fortschrittsbalken, solange das
  eingebettete Backend startet. Danach blendet er entweder zur App über (gültige
  Sitzung) oder das Login-Formular erscheint im selben Bild.
- Verbindungswarnungen von Reflex werden ausgeblendet, solange der Splash
  sichtbar ist (wie `splash.py` in vermoegen).
- Vorher prüfen: ob `LoginState` sich ohne die appkit-Seite ansprechen lässt
  und ob die OAuth-Callbacks mit eigener Login-Route funktionieren.

### Phase 5: Desktop-App mit eingebettetem Backend

- `rxconfig.py`: `DesktopPlugin` aus `reflex-desktop` nur bei
  `ALLOQ_DESKTOP=1`, Backend `embedded` auf festem Port (z. B. 18442),
  `transparent=True`, Fenster 1440×900, Mindestgröße 1100×700.
- Neues Profil `configuration/config.desktop.yaml`: `frontend_path` leer,
  `deploy_url` und `api_url` auf `127.0.0.1:<Port>`, `workers: 1`, zentrale
  Datenbank, CORS für `tauri://localhost`. Keine Hintergrundjobs im
  Desktop-Profil, sonst laufen sie auf jedem Rechner einmal.
- Aus vermoegen übernehmen: `scripts/desktop.py` (Python 3.14 statt 3.12),
  Desktop-Tasks im Taskfile, `tauri.conf.json` (`titleBarStyle: Overlay`,
  `hiddenTitle`, `trafficLightPosition` x 16 y 26, `transparent`,
  `windowEffects` sidebar), `app_menu.rs` mit deutschem App-Menü.
- Start der App prüft die Schema-Version der Datenbank gegen die erwartete
  Alembic-Revision und zeigt im Splash eine klare Meldung, wenn die App zu alt
  ist. Migrationen laufen nur auf dem Server.

## Risiken und offene Entscheidungen

1. **Zugangsdaten auf den Rechnern der Nutzer (blockiert Phase 5).** Das
   eingebettete Backend braucht heute Datenbankbenutzer und Passwort, den
   Verschlüsselungsschlüssel `common-db-encryption-key` und die
   OAuth-Client-Secrets. In einer verteilten App kann jeder Nutzer diese Werte
   auslesen und hätte damit vollen Zugriff auf die Datenbank. Möglichkeiten:
   - Datenbankanmeldung pro Nutzer mit Entra-ID-Token (Azure Database for
     PostgreSQL unterstützt das), OAuth als öffentlicher Client mit PKCE ohne
     Secret. Dafür muss appkit_user angepasst werden, und die Rechte in der
     Datenbank müssen pro Rolle gesetzt sein.
   - Ein schmaler API-Dienst auf dem Server, mit dem das eingebettete Backend
     spricht, statt direkt mit der Datenbank. Das ist sicher, aber deutlich
     mehr Arbeit.
   - Bewusst in Kauf nehmen, wenn nur ein kleiner, vertrauenswürdiger Kreis die
     App bekommt. Dann gehören die Werte in den macOS-Schlüsselbund und nicht
     ins Bundle.
2. **Netz.** Postgres muss von den Rechnern aus erreichbar sein (VPN oder
   Firewall-Regel). Jede Reflex-Aktion geht dann über das Netz zur Datenbank.
   Die Planungsansicht lädt viele Zeilen und sollte vorher gemessen werden.
3. **OAuth-Callbacks.** Azure und GitHub müssen die lokale Callback-Adresse
   (`http://127.0.0.1:<Port>/...`) als Redirect-URI kennen.
4. **Versionen.** reflex-desktop bündelt fest Python 3.12. vermoegen löst das
   mit `scripts/desktop.py`. Ob reflex-desktop mit Reflex 0.10.0 läuft, muss
   ein Spike zu Beginn von Phase 5 klären.

## Reihenfolge und Aufwand

| Phase | Ergebnis | Grobe Größe |
| --- | --- | --- |
| 1 | neues Farbschema überall sichtbar | klein |
| 2 | neuer Rahmen auf allen Seiten | groß |
| 3 | Listen mit Inspektor | mittel |
| 4 | Login im Splash-Stil | klein bis mittel |
| 5 | Desktop-App | groß, erst nach Entscheidung zu Risiko 1 |

Phase 1 bis 4 bringen den neuen Rahmen ins Web und lassen sich einzeln
ausliefern. Phase 5 startet mit einem Spike (reflex-desktop mit Reflex 0.10,
Verbindung zur zentralen Datenbank, Login über Microsoft).
