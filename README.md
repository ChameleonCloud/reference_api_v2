# Reference API

A REST API that serves hardware inventory data from the `reference-repository` git repo, with live node reservation availability from Blazar.

## Features

- Serves site, cluster, and node data from local JSON files.
- Provides simple HATEOAS-style links in API responses.
- Exposes git version information for the data repository.
- Auto-generates interactive API documentation (via Swagger UI).
- Live node availability synced from Blazar.

## Getting Started

### Prerequisites

- Python 3.12+
- `git`

### Installation

1.  **Clone this repository and initialize the data submodule:**

    ```bash
    git clone https://github.com/ChameleonCloud/reference_api_v2.git
    cd reference_api_v2
    git submodule update --init --recursive
    ```

2.  **Create a virtual environment and install dependencies:**

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install .[dev]
    ```

3.  **Run the development server:**

    ```bash
    uvicorn reference_api.main:app --reload
    ```

    The API will be available at `http://127.0.0.1:8000`. You can access the interactive API documentation at `http://127.0.0.1:8000/docs`.

## Configuration

The application can be configured via command-line arguments, environment variables, or a configuration file. The order of precedence is:

1.  Command-line arguments (highest)
2.  Environment variables
3.  `etc/config.toml` file
4.  Built-in defaults (lowest)

The config file is read at startup; the server must be restarted to pick up changes.

### `[server]`

| Key | Env var | Default | Description |
|-----|---------|---------|-------------|
| `host` | `REFERENCE_API_HOST` | `0.0.0.0` | Interface to bind. |
| `port` | `REFERENCE_API_PORT` | `8000` | Port to bind. |

### `[reference]`

| Key | Env var | Default | Description |
|-----|---------|---------|-------------|
| `ref_dir` | `REFERENCE_API_REF_DIR` | `reference-repository/data/chameleoncloud` | Path to the reference-repository data directory. Relative paths are resolved from the project root. |

### `[availability]`

Controls the background worker that polls Blazar for node reservation data.

| Key | Default | Description |
|-----|---------|-------------|
| `poll_interval_seconds` | `60` | How often (in seconds) each site is re-synced. |
| `site_timeout_seconds` | `120` | How long (in seconds) a single site sync may run before being cancelled. Blazar makes several serial API calls per sync, so allow headroom for slow endpoints. |
| `error_backoff_seconds` | `60` | How long (in seconds) the worker pauses after an unexpected error before retrying. |

### `[availability.sites.<site_id>]`

One section per site that should be synced. The `site_id` must match the `uid` field in the reference-repository data.

| Key | Description |
|-----|-------------|
| `cloud` | The cloud name as it appears in your `clouds.yaml`. |

**Example:**

```toml
[reference]
ref_dir = "reference-repository/data/chameleoncloud"

[availability]
poll_interval_seconds = 60
site_timeout_seconds = 120
error_backoff_seconds = 60

[availability.sites.uc]
cloud = "uc"

[availability.sites.tacc]
cloud = "tacc"
```

If no `[availability.sites.*]` sections are present the availability worker does not start and all availability responses will return `"unknown"`.

### CLI flags

| Flag | Description |
|------|-------------|
| `--host` | Interface to bind. |
| `--port` | Port to bind. |
| `--ref-dir` | Path to the reference-repository data directory. |
| `--debug` | Enable debug logging (no env var or config file equivalent). |

## Testing

```bash
pytest -q
```

Test fixtures live in `tests/data/chameleoncloud`, mirroring the reference-repository structure.

### Linting and type checking

```bash
pylint reference_api
mypy reference_api
```

## Container / Production

Build the image locally:

```bash
docker build -t reference-api:local .
```

Run the container:

```bash
docker run --rm -p 8000:8000 \
       -v $(pwd)/reference-repository:/app/reference-repository \
       reference-api:local
```

The availability worker needs a `clouds.yaml` resolvable by `openstacksdk` inside the container. Mount it at the standard location (`/etc/openstack/clouds.yaml` or `~/.config/openstack/clouds.yaml`) or set `OS_*` environment variables.

### Kubernetes: wiring up availability credentials

Create an application credential at each site (reader role is sufficient):

```bash
openstack application credential create reference-api --role reader
```

Package the populated `clouds.yaml` as a Secret and mount it into the container at `/etc/openstack/clouds.yaml`, then set `OS_CLIENT_CONFIG_FILE=/etc/openstack/clouds.yaml` in the container environment. The cloud names in `clouds.yaml` must match the `cloud` keys under `[availability.sites.*]` in `etc/config.toml`.

## CI / Publishing

`.github/workflows/ci.yml` runs lint, type-check, and tests on every PR. On push to `main` it builds and publishes a Docker image to GHCR:

- `ghcr.io/chameleoncloud/reference_api_v2:latest`
- `ghcr.io/chameleoncloud/reference_api_v2:<sha>`

On push to `develop` it publishes `ghcr.io/chameleoncloud/reference_api_v2:dev`.

## Notes

- Reference-repository JSON is cached in memory. Restart the service after updating files on disk.
- Node availability data is held in memory and refreshed every `poll_interval_seconds`. There is no persistent availability store; a fresh start begins with no availability data until the first sync completes.
