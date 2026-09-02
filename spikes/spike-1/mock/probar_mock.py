"""Smoke test HTTP con biblioteca estándar. No requiere pytest ni httpx."""

import argparse
import hashlib
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

SCENARIOS = {
    "completa": (["certificado_vigente", "declaracion_firmada"], ["cumple", "cumple"]),
    "vencido": (
        ["certificado_vencido", "declaracion_firmada"],
        ["no_cumple", "cumple"],
    ),
    "sin-firma": (
        ["certificado_vigente", "declaracion_sin_firma"],
        ["cumple", "no_cumple"],
    ),
    "faltante": (["certificado_vigente"], ["cumple", "faltante"]),
    "ilegible": (["ilegible"], ["no_evaluable", "no_evaluable"]),
    "revision": (
        ["certificado_fecha_dudosa", "declaracion_firma_dudosa"],
        ["requiere_revision", "requiere_revision"],
    ),
    "error": ([], []),
}


def demo_pdf() -> bytes:
    """PDF mínimo de una página. Su texto NO determina los resultados del mock."""
    stream = b"BT /F1 12 Tf 30 100 Td (SPIKE 1.3 - DOCUMENTO SIMULADO) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    result = b"%PDF-1.4\n"
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(result)
    result += b"xref\n0 6\n0000000000 65535 f \n"
    result += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    return (
        result
        + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    )


def run(base_url: str, scenario: str) -> None:
    owner = str(uuid4())

    def call(method, path, payload=None, binary=None, expected=200):
        body = (
            binary
            if binary is not None
            else (json.dumps(payload).encode() if payload is not None else None)
        )
        request = Request(
            base_url + path,
            data=body,
            method=method,
            headers={
                "X-Demo-User": owner,
                "Content-Type": "application/pdf"
                if binary is not None
                else "application/json",
            },
        )
        try:
            with urlopen(request, timeout=15) as response:
                if response.status != expected:
                    raise RuntimeError(
                        f"{method} {path}: esperado {expected}, recibido {response.status}"
                    )
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as error:
            raise RuntimeError(
                f"{method} {path}: HTTP {error.code}: {error.read().decode()}"
            ) from error

    def finish(job):
        first = call("GET", job["job_url"])
        if first["status"] != "processing":
            raise RuntimeError("No se observó el estado processing")
        terminal = call("GET", job["job_url"])
        if (
            terminal["status"] not in ("completed", "failed")
            or not terminal["simulated"]
        ):
            raise RuntimeError("Respuesta terminal inesperada")
        return terminal

    case = call(
        "POST", "/mock/expedientes", {"name": "Smoke - " + scenario}, expected=201
    )
    path = "/mock/expedientes/" + case["id"]

    def upload(kind, fixture):
        data = demo_pdf()
        created = call(
            "POST",
            path + "/uploads",
            {
                "kind": kind,
                "fixture": fixture,
                "filename": fixture + ".pdf",
                "size_bytes": len(data),
                "checksum_sha256": hashlib.sha256(data).hexdigest(),
            },
            expected=201,
        )
        call("PUT", created["upload_url"], binary=data, expected=204)

    upload("bases", "bases_demo")
    bases = finish(
        call(
            "POST",
            path + "/process",
            {
                "kind": "bases",
                "simulate_failure": scenario == "error",
            },
            expected=202,
        )
    )
    if scenario == "error":
        if bases["status"] != "failed" or bases["error"] is None:
            raise RuntimeError("No se obtuvo el fallo simulado esperado")
        print("OK [SIMULADO]: fallo de procesamiento notificado.")
        return
    call("POST", path + "/requirements/confirm", {"version": bases["bases_version"]})
    fixtures, expected = SCENARIOS[scenario]
    for fixture in fixtures:
        upload("propuesta", fixture)
    finish(call("POST", path + "/process", {"kind": "propuesta"}, expected=202))
    report = finish(call("POST", path + "/evaluations", expected=202))["result"]
    actual = [check["status"] for check in report["checks"]]
    if actual != expected:
        raise RuntimeError(f"Resultado incorrecto: {actual}, esperado {expected}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"OK [SIMULADO]: {scenario}. Estados: {actual}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8013")
    parser.add_argument("--escenario", choices=SCENARIOS, default="completa")
    args = parser.parse_args()
    if urlparse(args.url).hostname not in ("127.0.0.1", "localhost", "::1"):
        parser.error("Este mock es solo local; use una dirección loopback")
    try:
        run(args.url.rstrip("/"), args.escenario)
    except (RuntimeError, URLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
