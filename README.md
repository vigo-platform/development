# development

## Service configuration

Each service reads its own `<service>/.env`. This project uses Docker Compose
2.30 or later. From a fresh checkout, create the local files from their templates:

```sh
for template in */.env.example; do
  target="${template%.example}"
  if [ ! -e "$target" ]; then
    (umask 077; cp "$template" "$target")
  fi
done
```

Enter literal values without surrounding quotes. Fill in the Telegram settings
in `alertmanager/.env` before starting Alertmanager. If you change the
PostgreSQL credentials, update `auth/.env`, `user/.env`, and
`postgres-exporter/.env` to match. Service environment files belong in their
own directories. The stack can run without a root `.env`.

Compose controls published ports and bind mounts in `docker-compose.yml`.
Use `COMPOSE_AUTH_HOST_PORT`, `COMPOSE_USER_HOST_PORT`,
`COMPOSE_GATEWAY_HOST_PORT`, or `COMPOSE_REDIS_HOST_PORT` in the shell or an
optional root `.env` to customize published ports. If you previously set
`AUTH_PORT`, `USER_PORT`, `GATEWAY_PORT`, or `REDIS_PORT` to customize a host
port, move that setting to the corresponding `COMPOSE_*_HOST_PORT` variable.
Keep the service listener ports aligned with the container ports and scrape
targets in the repository.

## Auth

Compose runs `logtaha/vigo-auth-service:1.0.3` as `linux/amd64`.
Set `AUTH_OTP_SECRET` in `auth/.env` using `openssl rand -base64 32`.
Place `private_key.pem` and `public_key.pem` in `auth/.keys`. Compose mounts
that directory at `/app/.keys`. You can point the mount elsewhere by exporting
`AUTH_KEYS_DIR` before running Compose.

To enable metrics, generate a password with `openssl rand -hex 32`. Set
`AUTH_METRICS_PASSWORD` in `auth/.env` and put the same password in
`prometheus/secrets/auth_metrics_password`. Create the `secrets` directory
with mode 0700 and give the password file mode 0644 so the Prometheus
container can read its mounted copy. Create an empty file at that path
if you run Prometheus with auth scraping disabled.

```sh
docker compose pull auth user
docker compose up -d auth user
curl --fail http://localhost:8084/.well-known/jwks.json
```

Auth uses the `SERVER_PORT=8084` listener in `auth/.env` for its API, JWKS,
and metrics. Compose publishes it at `127.0.0.1:8084` by default.

For an existing deployment, set `SERVER_PORT=8084` and remove
`MANAGEMENT_SERVER_PORT` from `auth/.env`. Set `AUTH_PORT=8084` in
`gateway/.env` and `AUTH_JWKS_URI=http://auth:8084/.well-known/jwks.json`
in `user/.env`. Keep the other values in those files, then run
`docker compose up -d auth user gateway`.
Auth uses the Compose PostgreSQL and Redis services. Redis listens on port 6379
inside the network.
PostgreSQL creates `vigo_auth_service` when initializing a new volume.
If an existing volume predates that database, create it before starting auth.
By default, auth calls the user service at `user:50051`. Set `USER_GRPC_HOST`
and `USER_GRPC_PORT` in `auth/.env` to change that destination. If you
previously set `USER_GRPC_HOST` in the shell, move the value to `auth/.env`.

## User

Compose pulls `logtaha/vigo-user-service:1.0.0` for `linux/amd64`. Put the
server settings in `user/.env` using `user/.env.example` as a reference.
Match the database credentials in `postgres/.env` and the JWT issuer and
audience in `auth/.env`. User fetches signing keys from Auth on `app-network`.

HTTP is available on the host at `127.0.0.1:8081` by default. The gRPC port
`50051` and the management port `8082` are internal to Docker.
Update any saved PromQL queries using `job="app"` to use `job="auth"`.

PostgreSQL creates `vigo_user_service` when it initializes a fresh volume.
If your existing volume lacks this database, create it once before starting
User. If you have data in the older `vigo-user-service` database, migrate that
data to `vigo_user_service` before starting User.

```sh
docker compose up -d --wait postgres
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres' <<'SQL'
SELECT 'CREATE DATABASE vigo_user_service'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'vigo_user_service') \gexec
SQL
```

On a server already running the stack, deploy the updated files and `user/.env`,
then run the following to start User and load the new Prometheus configuration.

```sh
docker compose pull user
docker compose up -d --wait user auth
docker compose up -d --no-deps --force-recreate prometheus
docker compose ps user auth prometheus
```

The provided settings disable the Kafka outbox relay and use plaintext gRPC
on a trusted development network. Auth 1.0.3 requires a client upgrade for
production mTLS.

## Gateway

Compose runs `logtaha/vigo-gateway-service:1.0.0` as `linux/amd64` and reads
`gateway/.env`. Gateway uses `auth:8084` and `user:8081` on `app-network`.
It listens on `127.0.0.1:8080` on the host by default. Keep `SERVER_PORT=8080`
in `gateway/.env` to match the container port.

```sh
docker compose pull gateway
docker compose up -d gateway
curl --fail http://127.0.0.1:8080/actuator/health
curl --fail http://127.0.0.1:8080/.well-known/jwks.json
```

The files route requires a separately running Storage service. By default,
Gateway expects it at `storage:8083` on `app-network`. Set `STORAGE_HOST` and
`STORAGE_PORT` in `gateway/.env` if Storage uses a different address reachable
from the Gateway container.

## Prometheus

`prometheus/prometheus.yml` configures scraping and points to Alertmanager.
It scrapes `/actuator/prometheus` for the application jobs `auth` at
`auth:8084`, `user` at `user:8082`, and `gateway` at `gateway:8080`.
Auth serves metrics on the same listener as its API and requires HTTP Basic
authentication for the metrics endpoint.

`prometheus/alert_rules.yml` defines `InstanceDown` and `PostgresDown`.
Prometheus loads the rules through `rule_files` and sends firing alerts to
Alertmanager, which uses `alertmanager/alertmanager.yml.tmpl` for routing.

## Redis

The Redis service uses `redis:7`, reusing the local image when available.
Start it independently with:

```sh
docker compose up -d redis
docker compose exec redis redis-cli ping
```

The health check should return `PONG`. Connect from your machine at
`127.0.0.1:6379`, or from services on `app-network` at `redis:6379`.

Service settings are in `docker-compose.yml`; Redis uses its default server
settings without a separate configuration file. The `redis_data` volume stores
any snapshots Redis writes; AOF is disabled by default. The host port is bound
to localhost; no password is configured for this local development service.

## Kibana dashboard

After setting up the service environment files, run:

```sh
docker compose up -d
```

The `kibana-setup` service waits up to 10 minutes for Kibana, then imports
`dashboards/kibana/export.ndjson`, including its data view and visualizations.
It exits with code 0 after a successful import. Keep the entire `dashboards/kibana`
directory with the Compose file when copying or checking out this project on another machine.

Open [VIGO | Log Monitoring & Investigation](http://localhost:5601/app/dashboards#/view/92140dea-64ef-42ad-81da-9e7649d63bb9).
Panels populate when logs matching `app-logs*` arrive in Elasticsearch.

Each `docker compose up` reruns the completed setup service. Matching saved objects
are overwritten from the export without creating duplicates; export any UI changes
back to this file if you want to keep them on subsequent startups.

Check the import result or manually rerun it:

```sh
docker compose logs kibana-setup
docker compose run --rm kibana-setup
```

To run the importer directly on your machine while Kibana is running:

```sh
python3 dashboards/kibana/import_dashboard.py
```

Direct execution connects to `http://localhost:5601`; Compose sets `KIBANA_URL`
to `http://kibana:5601`. Set `KIBANA_URL` explicitly to target a different server.
While waiting, the script prints the connection error or Kibana status every 5 seconds.

Import uses Kibana's [saved objects import API](https://www.elastic.co/docs/api/doc/kibana/v8/operation/operation-importsavedobjectsdefault).
