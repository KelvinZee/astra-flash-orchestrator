#!/usr/bin/env python3
"""Read-only inspection of an existing Codex Router setup; no model requests."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11+ is required. No packages or settings were changed.")
import tomllib

DEFAULT_WORKER_MODEL = "gpt-5.6-luna"
DEFAULT_WORKER_EFFORT = "high"
# Backward-compatible alias used by the test fixtures and older integrations.
ROUTE = DEFAULT_WORKER_MODEL
ROLE = "astra_flash_builder"
SKILL = "astra-flash-orchestrator"

# Keys Codex reads as scalar settings directly under [agents]. Every other key
# there is read as an agent NAME whose value must be a role table, so a scalar
# under an unrecognized name makes Codex reject the entire config with
# "invalid type: ..., expected struct AgentRoleToml in `agents`" -- which takes
# down the host app and the CLI together, not just subagent routing.
AGENT_SCALAR_SETTINGS = frozenset({
    "enabled",
    "default_subagent_model",
    "default_subagent_reasoning_effort",
    "interrupt_message",
    "max_concurrent_threads_per_session",
    "max_threads",
    "max_depth",
    "job_max_runtime_seconds",
})


class SetupError(ValueError):
    """An actionable configuration problem, without credential-bearing details."""


def read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        # TOML errors can embed source text. Never echo them or a full config.
        raise SetupError(f"Cannot read valid TOML from {path.name} ({type(exc).__name__}).") from None


def merge_tables(base: dict, overlay: dict) -> dict:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_tables(result[key], value)
        else:
            result[key] = value
    return result


def resolve_path(value: str, home: Path, codex_home: Path) -> Path:
    value = value.replace("${CODEX_HOME}", str(codex_home)).replace("$CODEX_HOME", str(codex_home))
    value = value.replace("${HOME}", str(home)).replace("$HOME", str(home))
    if value == "~":
        value = str(home)
    elif value.startswith("~/"):
        value = str(home / value[2:])
    path = Path(value)
    return path if path.is_absolute() else codex_home / path


def model_entries(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("models", "data"):
            if isinstance(payload.get(key), list):
                return model_entries(payload[key])
    raise SetupError("Unrecognized model catalog structure; inspect it locally before installing.")


def model_id(entry: dict) -> str | None:
    return entry.get("slug") or entry.get("id")


def inspect(
    home: Path,
    codex_home: Path,
    profile: str | None = None,
    worker_model: str | None = None,
    worker_effort: str | None = None,
) -> tuple[dict, str]:
    """Return a redacted static report and a PRIVATE local URL. Do not print URL."""
    config_path = codex_home / "config.toml"
    config = read_toml(config_path)
    input_hashes = {str(config_path): hashlib.sha256(config_path.read_bytes()).hexdigest()}
    selected = profile if profile is not None else config.get("profile")
    warnings: list[str] = []
    if selected:
        if not isinstance(selected, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", selected):
            raise SetupError("Unsupported profile name; inspect the active profile manually.")
        standalone = codex_home / f"{selected}.config.toml"
        legacy = config.get("profiles", {}).get(selected)
        if standalone.exists() and legacy is not None:
            raise SetupError("Both standalone and legacy profile definitions exist; resolve that ambiguity first.")
        if standalone.exists():
            config = merge_tables(config, read_toml(standalone))
            input_hashes[str(standalone)] = hashlib.sha256(standalone.read_bytes()).hexdigest()
        elif isinstance(legacy, dict):
            config = merge_tables(config, legacy)
            warnings.append("A legacy inline profile was inspected; confirm your client still applies it.")
        else:
            raise SetupError("The selected profile is not available as a readable configuration file.")

    agents = config.get("agents", {})
    if not isinstance(agents, dict):
        raise SetupError("The existing [agents] setting is not a TOML table.")
    # Checking shape rather than a list of known top-level names catches any
    # absorbed key, not just the handful an installer happens to anticipate.
    misplaced = sorted(
        key for key, value in agents.items()
        if key not in AGENT_SCALAR_SETTINGS and not isinstance(value, dict)
    )
    if misplaced:
        raise SetupError(
            "Setting(s) that do not belong under [agents] were found there: "
            + ", ".join(misplaced)
            + ". In TOML, a table header remains active until the next table header, so a "
            "top-level key written after [agents] is absorbed into it; Codex then reads that "
            "key as an agent name and refuses to load the whole config. Move those keys above "
            "the first table header, or under the agent role they belong to, before installing. "
            "If your Codex build documents one of them as a genuine [agents] setting, it is newer "
            "than this check; verify with `codex doctor` rather than editing around this error."
        )
    if agents.get("enabled") is False:
        raise SetupError("Subagents are disabled in the inspected config. This installer will not enable them silently.")
    if "default_subagent_model" in agents:
        warnings.append(
            "The global default_subagent_model is not used or changed; the installed named role pins its own worker model."
        )
    requested_model = worker_model or os.environ.get("ASTRA_WORKER_MODEL") or DEFAULT_WORKER_MODEL
    requested_effort = worker_effort or os.environ.get("ASTRA_WORKER_EFFORT") or DEFAULT_WORKER_EFFORT
    if not isinstance(requested_model, str) or not requested_model.strip() or not re.fullmatch(r"[A-Za-z0-9._/-]+", requested_model):
        raise SetupError("The requested worker model id is invalid.")
    requested_model = requested_model.strip()
    if requested_effort is not None and (not isinstance(requested_effort, str) or not re.fullmatch(r"[a-z_]+", requested_effort)):
        raise SetupError("The requested worker reasoning effort is invalid.")
    if config.get("model") == requested_model:
        raise SetupError("The root model and implementation worker are the same. Select Astra as root or choose a different worker.")

    catalog_value = config.get("model_catalog_json")
    if not isinstance(catalog_value, str) or not catalog_value:
        raise SetupError("No model_catalog_json was found. Confirm the existing Codex Router configuration.")
    catalog_path = resolve_path(catalog_value, home, codex_home)
    try:
        if catalog_path.stat().st_size > 20_000_000:
            raise SetupError("The model catalog is unexpectedly large; inspect it manually.")
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise SetupError(f"Cannot read the configured model catalog ({type(exc).__name__}).") from None
    matches = [entry for entry in model_entries(payload) if model_id(entry) == requested_model]
    if len(matches) != 1:
        raise SetupError(
            f"The requested worker model {requested_model!r} is missing or duplicated in the local catalog. "
            "Use the router's own repair/publish process or choose another worker with --worker-model."
        )
    entry = matches[0]
    if entry.get("multi_agent_version") != "v2":
        raise SetupError(
            f"The requested worker {requested_model!r} exists but is not advertised for native subagents "
            "(multi_agent_version must be v2). Do not edit the catalog to bypass this gate. "
            "Choose a repository-certified/local-verified v2 worker, or wait for this exact route to become v2."
        )
    levels = entry.get("supported_reasoning_levels", [])
    supported = [x.get("effort") if isinstance(x, dict) else x for x in levels] if isinstance(levels, list) else []
    # The named role owns both worker settings. Do not couple installation to,
    # inherit, or encourage mutation of global defaults used by unrelated agents.
    effort = requested_effort or entry.get("default_reasoning_level")
    if effort is not None and (not isinstance(effort, str) or not re.fullmatch(r"[a-z_]+", effort)):
        raise SetupError("The worker reasoning effort is not a recognized string value.")
    if effort is not None and supported and effort not in supported:
        raise SetupError(
            f"The requested worker effort {effort!r} is not supported by {requested_model!r}. "
            f"Supported efforts: {', '.join(str(x) for x in supported)}."
        )
    if effort is None:
        warnings.append("No worker effort was pinned; inspect the actual spawned thread before relying on it.")

    provider = config.get("model_provider", "openai")
    if provider == "openai":
        url = config.get("openai_base_url", "")
    else:
        url = config.get("model_providers", {}).get(provider, {}).get("base_url", "")
    try:
        parsed = urlsplit(url)
        loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        # Codex Router supports both native authenticated /v1 and capability paths.
        # Keep exact path shapes; never accept arbitrary loopback API paths.
        route_path = parsed.path.rstrip("/")
        recognized_path = route_path == "/v1" or bool(re.fullmatch(r"/_codex-router/[A-Za-z0-9_-]+/v1", route_path))
        valid = parsed.scheme in {"http", "https"} and loopback and recognized_path
        valid = valid and not parsed.query and not parsed.fragment
        valid = valid and not parsed.username and not parsed.password
        _ = parsed.port
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise SetupError("The inspected provider does not point at a recognized loopback Codex Router URL. URL withheld.")
    if not config.get("model"):
        warnings.append("No root model is set in this config; select GPT-6 Astra in the new session UI.")
    if config.get("features", {}).get("multi_agent") is False:
        warnings.append("A legacy features.multi_agent=false flag exists; check whether your client honors it.")
    warnings.append("Project, CLI, UI and managed-policy overrides are not resolved by this static inspection.")
    report = {
        "status": "static-ready",
        "runtime_verified": False,
        "inference_request_made": False,
        "root_model_observed": config.get("model"),
        "root_effort_observed": config.get("model_reasoning_effort"),
        "worker_model": requested_model,
        "worker_effort": effort,
        "custom_agent": ROLE,
        "profile_inspected": selected,
        "catalog_contains_worker": True,
        "catalog_advertises_subagent": True,
        "loopback_router_configured": True,
        "input_hashes": input_hashes,
        "warnings": warnings,
    }
    return report, url


def default_locations(home_arg: str | None = None, codex_home_arg: str | None = None) -> tuple[Path, Path]:
    home = Path(home_arg).expanduser().resolve() if home_arg else Path.home().resolve()
    codex_home = Path(codex_home_arg or os.environ.get("CODEX_HOME", str(home / ".codex"))).expanduser().absolute()
    return home, codex_home
