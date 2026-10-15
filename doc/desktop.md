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

1. Microsoft-Entra-Authentifizierung aktivieren und einen Entra-Admin setzen.
2. Als Entra-Admin die Prinzipale anlegen, entweder je Person
   (`SELECT * FROM pgaadauth_create_principal('ada@firma.de', false, false);`)
   oder einmal für eine Entra-Gruppe, z. B. `alloq-desktop`.
   Bei einer Gruppe in `config.desktop.yaml` `db_role: alloq-desktop` setzen;
   die Personen melden sich dann mit dem Gruppennamen an.
3. Rechte vergeben, z. B. über eine Rolle `alloq_app`:

   ```sql
   GRANT USAGE ON SCHEMA public TO alloq_app;
   GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO alloq_app;
   GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO alloq_app;
   GRANT alloq_app TO "ada@firma.de";  -- oder TO "alloq-desktop"
   ```

4. Netzwerk: Der Server muss von den Rechnern aus erreichbar sein (VPN oder
   Firewall-Regel). TLS ist Pflicht (`ssl_mode: require`).

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
