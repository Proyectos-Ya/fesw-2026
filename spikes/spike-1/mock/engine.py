"""Reglas y fixtures del SPIKE. No lee ni interpreta el contenido de PDFs."""

from copy import deepcopy
from datetime import date

FIXTURES = {
    "bases_demo": {"kind": "bases"},
    "certificado_vigente": {
        "kind": "propuesta",
        "type": "certificado",
        "valid_until": "2026-12-31",
    },
    "certificado_vencido": {
        "kind": "propuesta",
        "type": "certificado",
        "valid_until": "2026-09-30",
    },
    "certificado_fecha_dudosa": {
        "kind": "propuesta",
        "type": "certificado",
        "valid_until": None,
    },
    "declaracion_firmada": {
        "kind": "propuesta",
        "type": "declaracion",
        "signature_present": True,
    },
    "declaracion_sin_firma": {
        "kind": "propuesta",
        "type": "declaracion",
        "signature_present": False,
    },
    "declaracion_firma_dudosa": {
        "kind": "propuesta",
        "type": "declaracion",
        "signature_present": None,
    },
    "ilegible": {"kind": "propuesta", "type": None, "unreadable": True},
}


def extract(documents: list[dict], kind: str) -> dict:
    if kind == "bases":
        evidence = {
            "document_id": documents[0]["id"],
            "filename": documents[0]["filename"],
            "page": 1,
            "simulated": True,
        }
        return {
            "requirements": [
                {
                    "id": "R1",
                    "type": "certificado",
                    "rule": "vigencia",
                    "reference_date": "2026-10-15",
                    "evidence": {
                        **evidence,
                        "quote": "Certificado vigente al cierre: 15/10/2026.",
                    },
                },
                {
                    "id": "R2",
                    "type": "declaracion",
                    "rule": "firma",
                    "evidence": {
                        **evidence,
                        "quote": "Se exige declaración jurada firmada.",
                    },
                },
            ]
        }
    return {
        "documents": [
            {
                **deepcopy(FIXTURES[d["fixture"]]),
                "evidence": {
                    "document_id": d["id"],
                    "filename": d["filename"],
                    "page": 1,
                    "fixture": d["fixture"],
                    "simulated": True,
                },
            }
            for d in documents
        ]
    }


def compare(requirements: list[dict], documents: list[dict]) -> list[dict]:
    checks = []
    for requirement in requirements:
        matches = [d for d in documents if d["type"] == requirement["type"]]
        uncertain = [d for d in documents if d.get("unreadable")]
        evidence = [d["evidence"] for d in matches]
        if not matches:
            status = "no_evaluable" if uncertain else "faltante"
            reason = (
                "Hay archivos ilegibles que podrían corresponder al requisito."
                if uncertain
                else "No se entregó un documento del tipo requerido."
            )
            evidence = [d["evidence"] for d in uncertain]
        elif len(matches) > 1:
            status, reason = (
                "requiere_revision",
                "Hay varios documentos candidatos; debe elegirse el aplicable.",
            )
        else:
            doc = matches[0]
            if requirement["rule"] == "vigencia":
                expiry = doc["valid_until"]
                if expiry is None:
                    status, reason = (
                        "requiere_revision",
                        "Fecha de vencimiento ambigua.",
                    )
                elif date.fromisoformat(expiry) < date.fromisoformat(
                    requirement["reference_date"]
                ):
                    status, reason = (
                        "no_cumple",
                        "El certificado vence antes de la fecha exigida en las bases.",
                    )
                else:
                    status, reason = (
                        "cumple",
                        "El certificado está vigente a la fecha exigida en las bases.",
                    )
            else:
                signature = doc["signature_present"]
                if signature is None:
                    status, reason = (
                        "requiere_revision",
                        "No se puede determinar la presencia de firma.",
                    )
                elif signature:
                    status, reason = (
                        "cumple",
                        "Presencia de firma simulada; autenticidad no verificada.",
                    )
                else:
                    status, reason = (
                        "no_cumple",
                        "La declaración no presenta firma en la extracción simulada.",
                    )
        checks.append(
            {
                "requirement_id": requirement["id"],
                "status": status,
                "reason": reason,
                "requirement_evidence": requirement["evidence"],
                "proposal_evidence": evidence,
            }
        )
    return checks
