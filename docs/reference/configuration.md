---
title: Configuration
description: How Alloq loads its YAML profiles, secrets and environment overrides, what each profile sets, and which keys and environment variables exist.
source_paths:
  - configuration/config.yaml
  - configuration/config.local.yaml
  - configuration/config.prod.yaml
  - configuration/config.devcontainer.yaml
  - configuration/config.docker_test.yaml
  - configuration/logging.yaml
  - configuration/logging.prod.yaml
  - app/__init__.py
  - app/configuration.py
  - app/public_url.py
  - rxconfig.py
  - tests/test_configuration_profiles.py
  - tests/test_public_url.py
  - tests/test_rxconfig.py
  - tests/test_configuration.py
last_verified_commit: "cb9d5b0 (v2.0.4)"
---

# Configuration

Alloq reads its settings from YAML files in `configuration/`, from secrets and from
environment variables. The loader comes from appkit_commons. This page explains
the loading order, lists every profile and key that Alloq uses, and names the
environment variables that change the behaviour.

## How the configuration is loaded

The app loads the configuration once, when the `app` package is imported:

1. [app/__init__.py](../../app/__init__.py) imports `appkit_commons`, which loads
   the `.env` file into the environment.
2. `configure()` in [app/configuration.py](../../app/configuration.py) builds a
   `Configuration[AppConfig]` and registers it, and each nested part, in the
   service registry.
3. `configure()` applies the public URL from `PUBLIC_BASE_URL` and
   `PUBLIC_PATH_PREFIX`. Without `PUBLIC_BASE_URL`, it raises a `RuntimeError` when
   `app.environment` is `production`.
4. [rxconfig.py](../../rxconfig.py) looks up `DatabaseConfig` and `ReflexConfig`
   in the registry and builds the Reflex `rx.Config` from them.

### Profiles

`config.yaml` is always loaded. The `PROFILES` environment variable is a
comma-separated list of extra profiles. For each name, the loader reads
`config.<name>.yaml` from the same folder and merges it on top, in the order of the
list. A later profile wins over an earlier one.

The merge is deep for maps. A list replaces the list from the earlier file
completely. `config.docker_test.yaml` uses this to remove every OAuth provider with
`oauth_providers: []`. A profile file that does not exist only logs a warning.

### Order of sources

The settings classes use pydantic-settings. A value is taken from the first source
that has it:

1. arguments passed in code
2. environment variables
3. the `.env` file
4. the YAML files, merged as described above

So an environment variable always wins over a YAML value.

`appkit_commons` loads `.env` with `load_dotenv(override=True)`. A value in `.env`
therefore replaces a variable with the same name that is already set in your shell.

### Environment overrides

Nested keys use a double underscore. The top-level keys `app` and `reflex` become
prefixes, e.g.:

```bash
APP__DATABASE__PORT=5433
APP__DATABASE__ECHO=true
REFLEX__FRONTEND_PORT=8081
```

`model_config = SettingsConfigDict(extra="ignore", env_nested_delimiter="__")` on
`BaseConfig` in appkit_commons sets this up.
[tests/test_configuration_profiles.py](../../tests/test_configuration_profiles.py)
removes every `APP__` and `REFLEX__` variable before it loads a profile, so these
overrides cannot leak into the test.

### Secrets

A value that starts with `secret:` is a reference. The loader replaces it with the
secret of that name before validation. `SECRET_PROVIDER` decides where the secret
comes from:

- `local` (the default) reads an environment variable. For `secret:alloq-db-user`
  it tries `alloq-db-user`, `ALLOQ-DB-USER`, `ALLOQ_DB_USER` and `alloq_db_user`, in
  this order. A missing secret raises `SecretNotFoundError`.
- `azure` reads the secret from Azure Key Vault. The vault address comes from
  `AZURE_KEY_VAULT_URL`, and the secret name is used in lower case.

These are the secret names that the YAML files refer to:

| Secret | Used for | Profiles |
| --- | --- | --- |
| `alloq-db-user` | `app.database.username` | base |
| `alloq-db-password` | `app.database.password` | base |
| `alloq-db-host` | `app.database.host` | base |
| `alloq-db-name` | `app.database.name` | base |
| `common-db-encryption-key` | `app.database.encryption_key` (Fernet key) | base |
| `common-oauth-azure-client-id` | Azure OAuth `client_id` | base |
| `common-oauth-azure-client-secret` | Azure OAuth `client_secret` | base |
| `common-oauth-azure-tenant-id` | Azure OAuth `tenant_id` | base |

`.env.example` and `docker-compose.yml` still use older names (`mn-db-user`,
`MN_DB_USER`, `avui-db-encryption-key`). They do not match the references above.

## Profiles

| File | Profile | Selected by | What it sets |
| --- | --- | --- | --- |
| `config.yaml` | `default` | always | Base values. Backend port `3030`, `frontend_path: /alloq`, database from secrets, `environment: production`, `logging.prod.yaml`, session timeout 25 minutes, token refresh 10 minutes, Azure as the OAuth provider |
| `config.local.yaml` | `local` | `PROFILES=local` | Local development. `deploy_url http://localhost:8080`, frontend port `8080`, one worker, `environment: local`, `logging.yaml`, auth server `http://localhost` port `8080` |
| `config.prod.yaml` | `prod` | `PROFILES=prod` | Production. `environment: production`, `logging.prod.yaml`, backend port `3030`, two workers |
| `config.devcontainer.yaml` | `devcontainer` | `PROFILES=devcontainer` | VS Code dev container. Frontend port `8080`, database `alloq-db` on host `db` with user and password `postgres` |
| `config.docker_test.yaml` | `docker_test` | `PROFILES=docker_test` in `docker-compose.yml` | Compose stack. Ports `8080` and `3030`, three workers, 300 second timeouts, database `alloq-db` on host `db`, no OAuth providers |

## Keys

### `profile`

The name of the profile. Every file sets it.

### `reflex`

These keys fill `ReflexConfig` from appkit_commons.

| Key | Default in code | Meaning |
| --- | --- | --- |
| `deploy_url` | `None` | Public address of the frontend |
| `api_url` | `None` | Address of the backend websocket |
| `frontend_port` | `80` | Port of the frontend |
| `backend_port` | `3030` | Port of the backend |
| `frontend_path` | `""` | Path prefix below which the app is served, e.g. `/alloq` |
| `workers` | `3` | Number of workers |
| `default_timeout` | `300` | Timeout in seconds |
| `backend_timeout` | `180` | Backend timeout in seconds |
| `single_port` | `False` | Serve frontend and backend on one port |

`rxconfig.py` passes only some of them to Reflex:

- `frontend_path` always.
- `frontend_port` and `backend_port`, but only when a YAML file sets them. A
  configured frontend port stops `reflex run --backend-only`, so `config.yaml` does
  not set one.
- `deploy_url` and `api_url`, but only when they are not empty.

`workers`, `default_timeout`, `backend_timeout` and `single_port` are read but not
passed to `rx.Config` at this commit. `task run:prod` and `start.sh` pass
`--single-port` on the command line instead.

### `app`

These keys fill `AppConfig` in [app/configuration.py](../../app/configuration.py).

| Key | Meaning |
| --- | --- |
| `version` | App version. `task release:build` updates it together with `pyproject.toml` |
| `name` | App name, `Alloq` |
| `logging` | File name of the logging setup in `configuration/`, e.g. `logging.yaml` |
| `environment` | One of `devcontainer`, `development`, `production`, `test`, `stage`, `docker`, `local`, `ci` |
| `trusted_proxies` | Addresses that may set `X-Forwarded-Proto`. Unset means every peer is trusted, and production logs a warning. A string is split at commas. `config.prod.yaml` reads it from `secret:common-allowed-proxies`; it is commented out in `config.yaml` |
| `database` | Database settings, see below |
| `authentication` | Sign-in settings, see below |

`config.yaml` also sets `app.backend_timeout: 180`. `AppConfig` has no field with
that name, and the loader ignores unknown keys, so this value has no effect.

### `app.database`

| Key | Default in code | Meaning |
| --- | --- | --- |
| `type` | `postgresql` | `postgresql` or `sqlite` |
| `username`, `password` | `postgres` | Credentials |
| `host`, `port`, `name` | `localhost`, `5432`, `postgres` | Server and database |
| `encryption_key` | empty | Fernet key for the stored OAuth tokens |
| `pool_size`, `max_overflow` | `10`, `30` | Connection pool size |
| `pool_recycle` | `1800` | Seconds after which a connection is renewed |
| `echo` | `False` | Log every SQL statement |
| `ssl_mode` | `disable` | One of `disable`, `allow`, `prefer`, `require`, `verify-ca`, `verify-full` |
| `url` | none | A full database URL that replaces the parts above |

### `app.authentication`

These keys fill `AuthenticationConfiguration` from appkit_user.

| Key | Value in Alloq | Meaning |
| --- | --- | --- |
| `session_timeout` | `25` | Minutes until a session ends |
| `auth_token_refresh_delta` | `10` | Minutes before the end when the token is refreshed |
| `server_url`, `server_port` | per profile | Public address used for links and OAuth callbacks |
| `oauth_providers` | Azure in `config.yaml` | List of OAuth providers. The GitHub entry is commented out |
| `public_routes` | login, password reset, OAuth callback | Routes reachable without a session. Everything else is denied |
| `login_rate_limit` | `5` per email, `20` per client, `15` minute window and lockout | Throttle for failed password logins |
| `password_reset` | `30` minute token, `3` requests per hour, `./assets/email-templates` | Reset link lifetime, request limit and email templates. The templates state the lifetime as fixed text, so change both together |
| `email_provider` | Azure in `config.prod.yaml`, mock in the other profiles | Sends the password reset emails. Without it, none are sent. Production needs the secrets `common-email-azure-connection-string` and `common-email-from-address` |

`session_cookie_secure` is `true` in `config.yaml`. The profiles `local`, `devcontainer` and
`docker_test` set it to `false` because they serve plain http. Production refuses to
start with `false`.

`reflex.trusted_proxy_hops` is the number of reverse proxies in front of the backend.
`config.yaml` sets `0`, which ignores `X-Forwarded-For`, and `config.prod.yaml` sets
`1`. The login throttle uses the resulting client address.

## Serving below a path prefix

In production a reverse proxy serves the app below a path such as `/alloq`. Two
variables describe the public address. [app/public_url.py](../../app/public_url.py)
reads them in `PublicUrl.from_env`.

| Variable | Meaning |
| --- | --- |
| `PUBLIC_BASE_URL` | Origin of the site, e.g. `https://apps.example.com`. It must be an http or https origin without a path, query or fragment |
| `PUBLIC_PATH_PREFIX` | The path prefix, e.g. `/alloq`. It is ignored, with a warning, when `PUBLIC_BASE_URL` is not set |

When `PUBLIC_BASE_URL` is set, `apply_public_url` replaces these values:

- `reflex.deploy_url` and `reflex.api_url` become the origin plus the prefix.
- `reflex.frontend_port` becomes `443` for https and `80` for http.
- `authentication.server_url` becomes the origin plus the prefix, and
  `server_port` becomes `0`.
- Every OAuth `redirect_url` becomes `<origin><prefix>/oauth/<provider>/callback`.

The README also names `REFLEX_FRONTEND_PATH`, `REFLEX_BACKEND_PATH` and
`REFLEX_API_URL` for the frontend export. Reflex reads them itself.

## Other environment variables

| Variable | Read by | Meaning |
| --- | --- | --- |
| `PROFILES` | appkit_commons | Extra profiles, see above |
| `SECRET_PROVIDER` | appkit_commons | `local` or `azure` |
| `AZURE_KEY_VAULT_URL` | appkit_commons | Key Vault address when `SECRET_PROVIDER=azure` |
| `UV_PROJECT_ENVIRONMENT` | uv | Folder of the virtual environment, `.venv.mac` in `.env.example` |
| `REFLEX_SOCKET_TIMEOUT` | Reflex | Set to `600` in `.env.example` |

## Logging

`app.logging` names a file in `configuration/`. `init_logging` from appkit_commons
loads it with `logging.config.dictConfig`. If the file does not exist, the default
logging setup stays.

- [configuration/logging.yaml](../../configuration/logging.yaml) is for
  development and prints colored output.
- [configuration/logging.prod.yaml](../../configuration/logging.prod.yaml) is for
  production and prints plain text without colors.

## Tests that guard the configuration

[tests/test_configuration_profiles.py](../../tests/test_configuration_profiles.py)
checks these rules for every `config*.yaml` file:

- `test_environment_is_valid_enum_value`: `app.environment` is a valid
  `Environment` value.
- `test_logging_file_exists`: the file in `app.logging` exists.
- `test_prod_logging_has_no_ansi_colors`: `logging.prod.yaml` uses no `colorlog`
  formatter.
- `test_profile_loads`: the `local` and `docker_test` profiles load, and
  `server_url` has no port, because appkit_user adds the port itself.
- `test_default_profile_requires_public_base_url`: the base profile refuses to start
  without `PUBLIC_BASE_URL`.
- `test_default_profile_derives_public_urls_from_env`: the public URL sets the auth
  server address and every OAuth callback.

[tests/test_public_url.py](../../tests/test_public_url.py) covers the parsing of
`PUBLIC_BASE_URL` and `PUBLIC_PATH_PREFIX`. [tests/test_rxconfig.py](../../tests/test_rxconfig.py)
covers which URLs and ports `rxconfig.py` passes to Reflex, and the error when no
database is configured. [tests/test_configuration.py](../../tests/test_configuration.py)
covers `AppConfig` and `configure()`.

## Open questions

- `.env.example` and `docker-compose.yml` use the secret names `mn-db-*` and
  `avui-db-encryption-key`, but `config.yaml` refers to `alloq-db-*` and
  `common-db-encryption-key`. Should the example files be updated?
- `reflex.workers`, `reflex.single_port`, both timeouts and `app.backend_timeout`
  are set in YAML but have no effect at this commit. Are they meant to be passed to
  Reflex?
