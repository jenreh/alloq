"""Desktop app (Tauri, embedded backend) against the central Postgres database.

No secrets ship with the app: every user signs in with Microsoft Entra ID
(public client, PKCE) and connects to Postgres with their own access token.
"""
