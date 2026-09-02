import unittest

from fastapi.testclient import TestClient

from mock_api import create_app


class FlowTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())
        self.client.headers["X-Demo-User"] = "11111111-1111-1111-1111-111111111111"
        response = self.client.post("/mock/expedientes", json={"name": "Demo"})
        self.assertEqual(response.status_code, 201)
        self.path = "/mock/expedientes/" + response.json()["id"]

    def upload(self, kind, fixture):
        data = b"%PDF-1.7\ncontenido simulado\n%%EOF"
        response = self.client.post(
            self.path + "/uploads",
            json={
                "kind": kind,
                "fixture": fixture,
                "filename": fixture + ".pdf",
                "size_bytes": len(data),
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        path = response.json()["upload_url"]
        response = self.client.put(path, content=data)
        self.assertEqual(response.status_code, 204, response.text)
        return path

    def finish(self, response):
        self.assertEqual(response.status_code, 202, response.text)
        path = response.json()["job_url"]
        first = self.client.get(path).json()
        self.assertEqual(first["status"], "processing")
        second = self.client.get(path).json()
        self.assertEqual(second, self.client.get(path).json())
        return second

    def process(self, kind, fail=False):
        return self.finish(
            self.client.post(
                self.path + "/process",
                json={
                    "kind": kind,
                    "simulate_failure": fail,
                },
            )
        )

    def prepare(self, fixtures):
        self.upload("bases", "bases_demo")
        self.assertEqual(self.process("bases")["status"], "completed")
        response = self.client.post(
            self.path + "/requirements/confirm", json={"version": 1}
        )
        self.assertEqual(response.status_code, 200, response.text)
        for fixture in fixtures:
            self.upload("propuesta", fixture)
        self.process("propuesta")

    def evaluate(self):
        job = self.finish(self.client.post(self.path + "/evaluations"))
        self.assertEqual(job["status"], "completed")
        self.assertTrue(job["simulated"])
        return job["result"]

    def test_complete(self):
        self.prepare(["certificado_vigente", "declaracion_firmada"])
        result = self.evaluate()
        self.assertEqual([r["status"] for r in result["checks"]], ["cumple", "cumple"])
        self.assertTrue(all(r["requirement_evidence"] for r in result["checks"]))

    def test_expired_unsigned_and_missing(self):
        for fixtures, expected in [
            (
                ["certificado_vencido", "declaracion_sin_firma"],
                ["no_cumple", "no_cumple"],
            ),
            (["certificado_vigente"], ["cumple", "faltante"]),
            (["ilegible"], ["no_evaluable", "no_evaluable"]),
            (
                ["certificado_fecha_dudosa", "declaracion_firma_dudosa"],
                ["requiere_revision", "requiere_revision"],
            ),
        ]:
            with self.subTest(fixtures=fixtures):
                self.setUp()
                self.prepare(fixtures)
                self.assertEqual(
                    [r["status"] for r in self.evaluate()["checks"]], expected
                )

    def test_confirmation_and_processing_required(self):
        self.assertEqual(self.client.post(self.path + "/evaluations").status_code, 409)
        self.upload("bases", "bases_demo")
        self.assertEqual(
            self.client.post(
                self.path + "/requirements/confirm", json={"version": 1}
            ).status_code,
            409,
        )
        self.process("bases")
        self.assertEqual(
            self.client.post(
                self.path + "/requirements/confirm", json={"version": 2}
            ).status_code,
            409,
        )

    def test_owner_isolation(self):
        self.upload("bases", "bases_demo")
        job = self.client.post(self.path + "/process", json={"kind": "bases"}).json()
        self.client.headers["X-Demo-User"] = "22222222-2222-2222-2222-222222222222"
        self.assertEqual(self.client.get(self.path).status_code, 404)
        self.assertEqual(self.client.get(job["job_url"]).status_code, 404)
        del self.client.headers["X-Demo-User"]
        self.assertEqual(self.client.get(self.path).status_code, 401)

    def test_versions_and_historical_report(self):
        self.prepare(["certificado_vigente", "declaracion_firmada"])
        response = self.client.post(self.path + "/evaluations")
        self.upload("bases", "bases_demo")
        result = self.finish(response)["result"]
        self.assertEqual(result["bases_version"], 1)
        self.assertEqual(self.client.post(self.path + "/evaluations").status_code, 409)
        self.assertEqual(self.client.get(self.path).json()["bases_version"], 2)

    def test_failure_is_stable_and_retryable(self):
        self.upload("bases", "bases_demo")
        failed = self.process("bases", fail=True)
        self.assertEqual(failed["status"], "failed")
        self.assertIsNotNone(failed["error"])
        self.assertEqual(self.process("bases")["status"], "completed")

    def test_upload_validation(self):
        payload = {
            "kind": "bases",
            "fixture": "bases_demo",
            "filename": "b.pdf",
            "size_bytes": 12,
        }
        response = self.client.post(self.path + "/uploads", json=payload)
        url = response.json()["upload_url"]
        self.assertEqual(self.client.put(url, content=b"not a pdf...").status_code, 422)
        self.assertEqual(
            self.client.post(
                self.path + "/process", json={"kind": "bases"}
            ).status_code,
            409,
        )
        payload["fixture"] = "certificado_vigente"
        self.assertEqual(
            self.client.post(self.path + "/uploads", json=payload).status_code, 422
        )
        payload.update(fixture="bases_demo", filename="b.exe")
        self.assertEqual(
            self.client.post(self.path + "/uploads", json=payload).status_code, 422
        )

    def test_upload_is_immutable(self):
        url = self.upload("bases", "bases_demo")
        self.assertEqual(self.client.put(url, content=b"%PDF").status_code, 409)

    def test_replacement_requires_reprocessing_and_preserves_report(self):
        self.prepare(["certificado_vencido", "declaracion_firmada"])
        old = self.evaluate()
        docs = self.client.get(self.path).json()["documents"]
        document_id = next(
            key
            for key, value in docs.items()
            if value["fixture"] == "certificado_vencido"
        )
        data = b"%PDF-1.7\nreplacement"
        response = self.client.post(
            self.path + "/uploads",
            json={
                "kind": "propuesta",
                "fixture": "certificado_vigente",
                "filename": "nuevo.pdf",
                "size_bytes": len(data),
                "replaces_document_id": document_id,
            },
        )
        self.assertEqual(response.status_code, 201)
        self.client.put(response.json()["upload_url"], content=data)
        self.assertEqual(self.client.post(self.path + "/evaluations").status_code, 409)
        self.process("propuesta")
        new = self.evaluate()
        self.assertEqual(old["checks"][0]["status"], "no_cumple")
        self.assertEqual(new["checks"][0]["status"], "cumple")
        self.assertGreater(new["propuesta_version"], old["propuesta_version"])

    def test_stale_extraction_does_not_ready_new_version(self):
        self.upload("bases", "bases_demo")
        job = self.client.post(self.path + "/process", json={"kind": "bases"})
        self.upload("bases", "bases_demo")
        self.finish(job)
        self.assertIsNone(self.client.get(self.path).json()["bases_ready"])

    def test_checksum_mismatch(self):
        data = b"%PDF-1.7\nmock"
        created = self.client.post(
            self.path + "/uploads",
            json={
                "kind": "bases",
                "fixture": "bases_demo",
                "filename": "b.pdf",
                "size_bytes": len(data),
                "checksum_sha256": "0" * 64,
            },
        )
        self.assertEqual(
            self.client.put(created.json()["upload_url"], content=data).status_code, 422
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
