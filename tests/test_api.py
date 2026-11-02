import os
import sys
import tempfile
import unittest

# banco temporario, definido ANTES de importar o app
_tmp = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(_tmp, "teste.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402


class ApiTarefasTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "ok")

    def test_crud_completo(self):
        r = self.client.post("/tarefas", json={"titulo": "Estudar Azure", "descricao": "VM e storage"})
        self.assertEqual(r.status_code, 201)
        tid = r.get_json()["id"]

        r = self.client.get(f"/tarefas/{tid}")
        self.assertEqual(r.get_json()["titulo"], "Estudar Azure")
        self.assertFalse(r.get_json()["concluida"])

        r = self.client.put(f"/tarefas/{tid}", json={"concluida": True})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["concluida"])

        r = self.client.get("/tarefas?concluida=1")
        self.assertIn(tid, [t["id"] for t in r.get_json()])

        r = self.client.delete(f"/tarefas/{tid}")
        self.assertEqual(r.status_code, 204)
        self.assertEqual(self.client.get(f"/tarefas/{tid}").status_code, 404)

    def test_validacao(self):
        self.assertEqual(self.client.post("/tarefas", json={}).status_code, 400)
        self.assertEqual(self.client.post("/tarefas", json={"titulo": "  "}).status_code, 400)
        self.assertEqual(self.client.post("/tarefas", json={"titulo": "x" * 121}).status_code, 400)
        self.assertEqual(self.client.post("/tarefas", data="nao e json").status_code, 400)

    def test_sql_injection_nao_funciona(self):
        r = self.client.post("/tarefas", json={"titulo": "x'); DROP TABLE tarefas;--"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.client.get("/tarefas").status_code, 200)

    def test_404(self):
        self.assertEqual(self.client.get("/nao-existe").status_code, 404)
        self.assertEqual(self.client.put("/tarefas/9999", json={"titulo": "a"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
