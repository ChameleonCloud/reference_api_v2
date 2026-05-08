import argparse
import os
import tomllib

from pathlib import Path

import uvicorn


def main():
    repo_root = Path(__file__).resolve().parents[1]
    cfg_path = repo_root / "etc" / "config.toml"
    cfg = {}
    if cfg_path.exists():
        try:
            with open(cfg_path, "rb") as f:
                cfg = tomllib.load(f)
        except (tomllib.TOMLDecodeError, OSError):
            cfg = {}

    ref_cfg = cfg.get("reference", {})
    server_cfg = cfg.get("server", {})

    default_ref = (
        os.environ.get("REFERENCE_API_REF_DIR")
        or ref_cfg.get("ref_dir", "reference-repository/data/chameleoncloud")
    )
    default_host = (
        os.environ.get("REFERENCE_API_HOST")
        or server_cfg.get("host", "0.0.0.0")
    )
    _port_env = os.environ.get("REFERENCE_API_PORT")
    default_port = int(_port_env) if _port_env else int(server_cfg.get("port", 8000))

    parser = argparse.ArgumentParser(prog="reference-api")

    parser.add_argument(
        "--ref-dir",
        dest="ref_dir",
        default=default_ref,
        help="Path to reference repository data directory"
    )

    parser.add_argument(
        "--host",
        default=default_host,
    )

    parser.add_argument(
        "--port",
        type=int,
        default=default_port,
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    log_level = "debug" if args.debug else "info"
    uvicorn.run(
        "reference_api.main:app",
        host=args.host,
        port=args.port,
        log_level=log_level
    )


if __name__ == "__main__":
    main()
