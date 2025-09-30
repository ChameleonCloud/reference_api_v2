# Reference API

This is a REST API app that serves JSON data from the `reference-repository` git repo.

## Features

- Serves site, cluster, and node data from local JSON files.
- Provides simple HATEOAS-style links in API responses.
- Exposes git version information for the data repository.
- Auto-generates interactive API documentation (via Swagger UI).

## Getting Started

### Prerequisites

- Python 3.12+
- `git`

### Installation

1.  **Clone this repository and initialize the data submodule:**
    This project expects a `reference-repository` directory containing the JSON data files.

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

**Example using CLI arguments:**

```bash
uvicorn reference_api.main:app --host 127.0.0.1 --port 8000
```

An example configuration file is provided at `etc/config.toml`.

## Testing

Run the unit and integration tests using `pytest`:
```bash
pytest -q
```

Test fixtures are loaded from `tests/data/chameleoncloud`, which mirrors the structure of the main data repository.

### Linting

`pylint` is used for linting. To run the linter:
```bash
pylint reference_api
```

### Type Checking

`mypy` is used for static type checking. To run the type checker:
```bash
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

## CI / Publishing

A GitHub Actions workflow is included at `.github/workflows/ci.yml`. It will run tests on every PR and, when changes are pushed to `main`, build and publish a Docker image to GitHub Container Registry (GHCR). The workflow uses the repository's `GITHUB_TOKEN` for authentication.

## Notes

The reference-repository data is cached in memory, so if the service is running
and the data in the reference-repository is updated on disk, the service should
be restarted to load the updated data.
