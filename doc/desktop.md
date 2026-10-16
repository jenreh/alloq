# alloq als Desktop-App

Die Desktop-App ist eine Tauri-App mit eingebettetem Python-Backend
(reflex-desktop). Sie nutzt die zentrale Postgres-Datenbank und enthält keine
Geheimnisse: Jede Person meldet sich mit Microsoft Entra ID an und verbindet
sich mit ihrem eigenen Zugriffstoken mit Postgres.

## Ablauf der Anmeldung

1. „Mit Microsoft anmelden“ nutzt zuerst das gespeicherte Konto aus dem
   macOS-Schlüsselbund (Eintrag `alloq` / `entra-token-cache`). Gibt es keins,
   öffnet MSAL die Anmeldung im Standardbrowser (Authorization Code Flow mit
   PKCE, Rückleitung auf `http://localhost`).
2. Jede neue Datenbankverbindung bekommt Benutzer und Token der angemeldeten
   Person (`app/desktop/entra.py`). Vor der Anmeldung gibt es keine
   Verbindung.
3. Die App prüft die Schema-Version (`alembic_version`) gegen
   `app/desktop/schema.py`. Passt sie nicht, bricht die Anmeldung mit einem
   Hinweis ab. Migrationen laufen nur auf dem Server.
4. Die App sucht den alloq-Benutzer mit derselben E-Mail-Adresse (Groß- und
   Kleinschreibung egal) und öffnet die normale appkit-Sitzung. Neue Benutzer
   legt die Desktop-App nicht an.

Nach einem Neustart stellt die App das Microsoft-Konto aus dem Schlüsselbund
still wieder her, sobald sie die Datenbank braucht. Ist die alloq-Sitzung noch
gültig, geht es ohne Anmeldeseite weiter. Das Zugriffstoken erneuert ein
Hintergrund-Thread kurz vor Ablauf.

„Abmelden“ beendet die Sitzung, vergisst das Microsoft-Konto auf diesem Mac und
schließt alle Datenbankverbindungen.

## Einrichtung in Azure (einmalig)

### App-Registrierung

Die Werte stehen in `configuration/config.desktop.yaml` unter `app.desktop`.
Die Datei verweist mit `secret:` auf die Einträge der Web-App; beim Build
löst `scripts/desktop.py` sie auf und schreibt die Werte in die App.
Erlaubt ist das nur für öffentliche Kennungen (`tenant_id`, `client_id`,
`host`, `name`); jedes andere `secret:` bricht den Build ab.

Die Registrierung braucht:

- Plattform „Mobile und Desktopanwendungen“ mit der Umleitungs-URI
  `http://localhost`.
- „Öffentliche Clientflows zulassen“: Ja. Die Desktop-App sendet kein
  Client-Secret.
- Delegierte API-Berechtigung „Azure OSSRDBMS Database“ →
  `user_impersonation`, mit Administratorzustimmung.

Wird dieselbe Registrierung wie für die Web-App genutzt, gelten diese
Einstellungen zusätzlich zur Web-Plattform.

### Postgres (Azure Database for PostgreSQL, Flexible Server)

1. Microsoft-Entra-Authentifizierung aktivieren und die erste Person als
   Entra-Admin setzen (Typ „User“, ihr UPN). In knowledgeai-container ist das
   `pg_entra_admin`. Diese Person ist Datenbank-Admin und meldet sich wie alle
   anderen mit ihrem eigenen Konto an; `db_role` bleibt leer.
2. Die Migration `ee66ff77aa88` legt auf dem Server die Rolle
   `<datenbank>_app` an (`alloq_app`). Sie darf alle Tabellen lesen und ändern,
   auch die späterer Migrationen, aber das Schema nicht ändern. Anschließend
   vergibt der Ersteller der Rolle einmalig die Mitgliedschaft mit
   `ADMIN OPTION` an den tatsächlichen Entra-Admin-Prinzipal. Beispiel für die
   Datenbank `alloq` (UPN durch den vorhandenen Postgres-Prinzipal ersetzen):

   ```sql
   GRANT alloq_app TO "admin@example.com" WITH ADMIN OPTION;
   ```

   Die geschützte Azure-Systemrolle `azure_pg_admin` darf dabei nicht verändert
   werden. Ihre Mitgliedschaft allein ersetzt diese explizite Berechtigung
   in der Desktop-App nicht. Weitere Datenbank-Admins erhalten denselben Grant;
   normale Desktop-Benutzer erhalten die Rolle ohne `ADMIN OPTION`.
3. Zugriff vergeben: Die erste Person öffnet in der Desktop-App
   „Administration · Benutzer“ und klickt in der Zeile einer Person auf das
   Datenbank-Symbol. Die App legt den Entra-Prinzipal der Person an (falls es
   ihn noch nicht gibt) und gibt ihr die Rolle. Ein zweiter Klick entzieht die
   Rolle wieder. Grün heißt: hat Zugriff.
4. Netzwerk: Der Server muss von den Rechnern aus erreichbar sein (VPN oder
   Firewall-Regel). TLS ist Pflicht (`ssl_mode: require`).

Das Datenbank-Symbol gibt es nur in der Desktop-App, denn nur dort verbindet
sich die App mit dem Konto der angemeldeten Person. Ohne Admin-Rechte in der
Datenbank zeigt es den Zugriff nur an. Die E-Mail-Adresse in alloq muss dem
Microsoft-Anmeldenamen (UPN) entsprechen, auch in der Groß- und
Kleinschreibung, denn Postgres meldet die Person mit diesem Namen an.

Wichtig: Wer Datenbankrechte hat, kann mit seinem Token auch direkt auf die
Datenbank zugreifen, an den Admin-Prüfungen der App vorbei. Die Rolle deshalb
nur Personen geben, die in alloq Administratorrechte haben.

## Bauen und starten

```bash
task desktop:doctor
```

```bash
task desktop:run
```

```bash
task desktop:build
```

`task desktop:dev` startet die App mit Hot Reload gegen den Entwicklungsserver,
mit vorgetäuschter Anmeldung als `admin@aila-solutions.com` gegen die lokale
Datenbank (siehe unten). Ein anderer Benutzer:
`ALLOQ_FAKE_ENTRA_EMAIL=<email> task desktop:dev`.
Das Desktop-Profil gilt, sobald `ALLOQ_DESKTOP=1` gesetzt ist oder die App im
Bundle läuft (`app/desktop/profile.py`).

### Testen ohne Microsoft-Anmeldung

Für Entwicklung und Tests lässt sich die Anmeldung vortäuschen:

```bash
ALLOQ_DESKTOP=1 ALLOQ_FAKE_ENTRA_EMAIL=admin@aila-solutions.com uv run reflex run
```

„Mit Microsoft anmelden“ meldet dann ohne Browser als dieser alloq-Benutzer
an, und die Datenbank nutzt die lokalen Zugangsdaten (Profil
`desktop_fake`, Frontend auf Port 18443). Eine abweichende Schema-Version ist
dabei nur eine Warnung. Im App-Bundle wird die Variable ignoriert, und der
Build packt das Profil `desktop_fake` nie ein. Läuft daneben der normale
Entwicklungsserver, mit `REFLEX_WEB_WORKDIR=<anderer Ordner>` einen eigenen
`.web`-Ordner nutzen.

Nach einer neuen Migration muss `KNOWN_REVISIONS` in `app/desktop/schema.py`
ergänzt werden; ein Test erinnert daran.

# alloq als Desktop-App

Die Desktop-App ist eine Tauri-App mit eingebettetem Python-Backend
(reflex-desktop). Sie nutzt die zentrale Postgres-Datenbank und enthält keine
Geheimnisse: Jede Person meldet sich mit Microsoft Entra ID an und verbindet
sich mit ihrem eigenen Zugriffstoken mit Postgres.

## Ablauf der Anmeldung

1. „Mit Microsoft anmelden“ nutzt zuerst das gespeicherte Konto aus dem
   macOS-Schlüsselbund (Eintrag `alloq` / `entra-token-cache`). Gibt es keins,
   öffnet MSAL die Anmeldung im Standardbrowser (Authorization Code Flow mit
   PKCE, Rückleitung auf `http://localhost`).
2. Jede neue Datenbankverbindung bekommt Benutzer und Token der angemeldeten
   Person (`app/desktop/entra.py`). Vor der Anmeldung gibt es keine
   Verbindung.
3. Die App prüft die Schema-Version (`alembic_version`) gegen
   `app/desktop/schema.py`. Passt sie nicht, bricht die Anmeldung mit einem
   Hinweis ab. Migrationen laufen nur auf dem Server.
4. Die App sucht den alloq-Benutzer mit derselben E-Mail-Adresse (Groß- und
   Kleinschreibung egal) und öffnet die normale appkit-Sitzung. Neue Benutzer
   legt die Desktop-App nicht an.

Nach einem Neustart stellt die App das Microsoft-Konto aus dem Schlüsselbund
still wieder her, sobald sie die Datenbank braucht. Ist die alloq-Sitzung noch
gültig, geht es ohne Anmeldeseite weiter. Das Zugriffstoken erneuert ein
Hintergrund-Thread kurz vor Ablauf.

„Abmelden“ beendet die Sitzung, vergisst das Microsoft-Konto auf diesem Mac und
schließt alle Datenbankverbindungen.

## Einrichtung in Azure (einmalig)

### App-Registrierung

Die Werte stehen in `configuration/config.desktop.yaml` unter `app.desktop`.
Die Datei verweist mit `secret:` auf die Einträge der Web-App; beim Build
löst `scripts/desktop.py` sie auf und schreibt die Werte in die App.
Erlaubt ist das nur für öffentliche Kennungen (`tenant_id`, `client_id`,
`host`, `name`); jedes andere `secret:` bricht den Build ab.

Die Registrierung braucht:

- Plattform „Mobile und Desktopanwendungen“ mit der Umleitungs-URI
  `http://localhost`.
- „Öffentliche Clientflows zulassen“: Ja. Die Desktop-App sendet kein
  Client-Secret.
- Delegierte API-Berechtigung „Azure OSSRDBMS Database“ →
  `user_impersonation`, mit Administratorzustimmung.

Wird dieselbe Registrierung wie für die Web-App genutzt, gelten diese
Einstellungen zusätzlich zur Web-Plattform.

### Postgres (Azure Database for PostgreSQL, Flexible Server)

1. Microsoft-Entra-Authentifizierung aktivieren und die erste Person als
   Entra-Admin setzen (Typ „User“, ihr UPN). In knowledgeai-container ist das
   `pg_entra_admin`. Diese Person ist Datenbank-Admin und meldet sich wie alle
   anderen mit ihrem eigenen Konto an; `db_role` bleibt leer.
2. Die Migration `ee66ff77aa88` legt auf dem Server die Rolle
   `<datenbank>_app` an (`alloq_app`). Sie darf alle Tabellen lesen und ändern,
   auch die späterer Migrationen, aber das Schema nicht ändern. Die
   Datenbank-Admins (`azure_pg_admin`) dürfen sie weitergeben.
3. Zugriff vergeben: Die erste Person öffnet in der Desktop-App
   „Administration · Benutzer“ und klickt in der Zeile einer Person auf das
   Datenbank-Symbol. Die App legt den Entra-Prinzipal der Person an (falls es
   ihn noch nicht gibt) und gibt ihr die Rolle. Ein zweiter Klick entzieht die
   Rolle wieder. Grün heißt: hat Zugriff.
4. Netzwerk: Der Server muss von den Rechnern aus erreichbar sein (VPN oder
   Firewall-Regel). TLS ist Pflicht (`ssl_mode: require`).

Das Datenbank-Symbol gibt es nur in der Desktop-App, denn nur dort verbindet
sich die App mit dem Konto der angemeldeten Person. Ohne Admin-Rechte in der
Datenbank zeigt es den Zugriff nur an. Die E-Mail-Adresse in alloq muss dem
Microsoft-Anmeldenamen (UPN) entsprechen, auch in der Groß- und
Kleinschreibung, denn Postgres meldet die Person mit diesem Namen an.

Wichtig: Wer Datenbankrechte hat, kann mit seinem Token auch direkt auf die
Datenbank zugreifen, an den Admin-Prüfungen der App vorbei. Die Rolle deshalb
nur Personen geben, die in alloq Administratorrechte haben.

## Bauen und starten

```bash
task desktop:doctor
```

```bash
task desktop:run
```

```bash
task desktop:build
```

`task desktop:dev` startet die App mit Hot Reload gegen den Entwicklungsserver,
mit vorgetäuschter Anmeldung als `admin@aila-solutions.com` gegen die lokale
Datenbank (siehe unten). Ein anderer Benutzer:
`ALLOQ_FAKE_ENTRA_EMAIL=<email> task desktop:dev`.
Das Desktop-Profil gilt, sobald `ALLOQ_DESKTOP=1` gesetzt ist oder die App im
Bundle läuft (`app/desktop/profile.py`).

### Testen ohne Microsoft-Anmeldung

Für Entwicklung und Tests lässt sich die Anmeldung vortäuschen:

```bash
ALLOQ_DESKTOP=1 ALLOQ_FAKE_ENTRA_EMAIL=admin@aila-solutions.com uv run reflex run
```

„Mit Microsoft anmelden“ meldet dann ohne Browser als dieser alloq-Benutzer
an, und die Datenbank nutzt die lokalen Zugangsdaten (Profil
`desktop_fake`, Frontend auf Port 18443). Eine abweichende Schema-Version ist
dabei nur eine Warnung. Im App-Bundle wird die Variable ignoriert, und der
Build packt das Profil `desktop_fake` nie ein. Läuft daneben der normale
Entwicklungsserver, mit `REFLEX_WEB_WORKDIR=<anderer Ordner>` einen eigenen
`.web`-Ordner nutzen.

Nach einer neuen Migration muss `KNOWN_REVISIONS` in `app/desktop/schema.py`
ergänzt werden; ein Test erinnert daran.
