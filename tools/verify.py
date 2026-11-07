#!/usr/bin/env python3
"""Valida el contrato de Andromeda sin dependencias externas.

Comprueba:
  - JSON valido y version coherente.
  - Politicas y limites con la forma esperada.
  - Codigos de error y su HTTP.
  - Vectores de peticion/respuesta.
  - Huellas SHA-256 de la copia vendorizada, si existe SHA256SUMS.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "home-api-v1"
REQUIRED_POLICIES = {
    "gateway",
    "remote_voice",
    "voice_message",
    "camera_stream",
    "pairing",
    "auth",
    "transport",
}
POLICY_RE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*_v[0-9]+$")
ERROR_RE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load(path: Path):
    try:
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)
    except FileNotFoundError:
        fail(f"falta {path.relative_to(ROOT)}")
    except json.JSONDecodeError as error:
        fail(f"JSON invalido en {path.relative_to(ROOT)}: {error}")


def main() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        fail(f"VERSION invalida: {version!r}")
    major = int(version.split(".")[0])

    policies = load(API / "policies.json")
    limits = load(API / "limits.json")
    errors = load(API / "errors.json")
    spec = load(API / "openapi.json")

    for label, document in (
        ("policies", policies),
        ("limits", limits),
        ("errors", errors),
    ):
        if document.get("contract") != major:
            fail(f"{label}.contract no coincide con VERSION {version}")

    missing = REQUIRED_POLICIES - set(policies)
    if missing:
        fail(f"faltan politicas: {sorted(missing)}")
    for key, value in policies.items():
        if key == "contract":
            continue
        if not isinstance(value, str) or not POLICY_RE.fullmatch(value):
            fail(f"politica invalida {key}={value!r}")
        if len(value) > 64:
            fail(f"la politica {key} es demasiado larga para ser un nombre")

    for key, value in limits.items():
        if key == "contract":
            continue
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            fail(f"limite invalido {key}={value!r}")
    if limits["camera_viewers"] != 1:
        fail("camera_viewers debe ser 1")
    if limits["message_bytes"] > 4 * 1024 * 1024:
        fail("message_bytes supera el maximo de seguridad")
    if limits["command_wait_ms"] > 30000:
        fail("command_wait_ms supera el maximo de seguridad")

    for code, http in errors.get("http", {}).items():
        if not ERROR_RE.fullmatch(code):
            fail(f"codigo de error invalido: {code!r}")
        if not isinstance(http, int) or not 400 <= http <= 599:
            fail(f"HTTP invalido para {code}: {http!r}")

    if spec.get("openapi") != "3.1.0":
        fail("openapi.json debe declarar OpenAPI 3.1.0")
    if spec.get("info", {}).get("version") != version:
        fail("info.version no coincide con VERSION")
    paths = spec.get("paths", {})
    for required in ("/health", "/capabilities", "/pair", "/command", "/messages/{id}", "/camera/stream"):
        if required not in paths:
            fail(f"openapi.json no define {required}")

    vectors = sorted((API / "vectors").glob("*.json"))
    if not vectors:
        fail("no hay vectores")
    names: set[str] = set()
    for path in vectors:
        vector = load(path)
        name = vector.get("name")
        if not isinstance(name, str) or not name:
            fail(f"{path.name} no tiene name")
        if name in names:
            fail(f"vector duplicado: {name}")
        names.add(name)
        request = vector.get("request", {})
        response = vector.get("response", {})
        if request.get("method") not in {"GET", "POST", "PUT", "DELETE"}:
            fail(f"{name}: metodo invalido")
        if not str(request.get("path", "")).startswith("/v1/"):
            fail(f"{name}: path invalido")
        status = response.get("status")
        if not isinstance(status, int) or not 100 <= status <= 599:
            fail(f"{name}: status invalido")
        if status >= 400:
            body = response.get("body", {})
            code = body.get("error")
            if code not in errors["http"]:
                fail(f"{name}: error desconocido {code!r}")
            if errors["http"][code] != status:
                fail(f"{name}: {code} deberia ser {errors['http'][code]}, no {status}")

    sums = ROOT / "SHA256SUMS"
    if sums.exists():
        for line in sums.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                fail(f"SHA256SUMS invalido: {line!r}")
            digest, relative = parts
            target = ROOT / relative.strip()
            if not target.exists():
                fail(f"falta {relative.strip()}")
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual != digest:
                fail(f"huella distinta en {relative.strip()}")

    print(
        f"OK: contrato {version}, {len(vectors)} vectores, "
        f"{len(policies) - 1} politicas, {len(limits) - 1} limites"
    )


if __name__ == "__main__":
    main()
