# API de Tarefas (Flask + SQLite) hospedada em VM na Azure

API REST básica de tarefas (CRUD) feita em **Python + Flask**, com banco **SQLite**, publicada de ponta a ponta em uma **VM Linux na Azure** (gunicorn + systemd).

Atividade de Cloud — FIAP, Prof. Eduardo Popovici.

- Autor: Victor Marcolongo Pereira
- Documentação completa (PDF): `docs/Documentacao-API-Tarefas.pdf` (gerada por `docs/gerar_pdf.py`)

## Arquitetura

```
Cliente (curl / navegador) --HTTP:80--> NSG (porta 80) --> VM Ubuntu 22.04 (Standard_B1s)
                                                           gunicorn (2 workers) --> Flask --> SQLite (/var/lib/api-tarefas/tarefas.db)
                                                           disco de SO Standard SSD 30 GiB
```

Diagramas em `docs/diagramas/`.

## Rotas

| Método | Rota             | Descrição                                   | Sucesso |
|--------|------------------|---------------------------------------------|---------|
| GET    | `/`              | Informações da API                          | 200     |
| GET    | `/health`        | Verifica API e acesso ao banco              | 200     |
| GET    | `/tarefas`       | Lista tarefas (`?concluida=0` ou `1`)       | 200     |
| GET    | `/tarefas/<id>`  | Busca uma tarefa                            | 200     |
| POST   | `/tarefas`       | Cria tarefa (`titulo` obrigatório)          | 201     |
| PUT    | `/tarefas/<id>`  | Atualiza `titulo`, `descricao`, `concluida` | 200     |
| DELETE | `/tarefas/<id>`  | Remove tarefa                               | 204     |

Erros retornam JSON `{"erro": "..."}` com 400 (validação) ou 404.

## Rodar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py            # http://127.0.0.1:5000
python -m unittest discover -s tests -v
```

## Exemplos com curl

```bash
curl http://127.0.0.1:5000/health
curl -X POST http://127.0.0.1:5000/tarefas -H 'Content-Type: application/json' \
     -d '{"titulo":"Estudar Azure","descricao":"VM e storage"}'
curl http://127.0.0.1:5000/tarefas
curl -X PUT http://127.0.0.1:5000/tarefas/1 -H 'Content-Type: application/json' -d '{"concluida":true}'
curl -X DELETE http://127.0.0.1:5000/tarefas/1
```

## Deploy na Azure

1. **Infraestrutura** (Azure Cloud Shell ou `az` logado): `bash deploy/azure-cli.sh`
   Cria o grupo de recursos, a VM `Standard_B1s` (Ubuntu 22.04, disco Standard SSD 30 GiB, IP público) e abre a porta 80.
2. **Código no GitHub**: https://github.com/vlongo404/GS-cloud (repositório **público**, para a VM clonar sem credenciais).
3. **Configurar a VM**: `ssh azureuser@<IP_PUBLICO>` e rodar
   `curl -O https://raw.githubusercontent.com/vlongo404/GS-cloud/main/deploy/setup-vm.sh && bash setup-vm.sh https://github.com/vlongo404/GS-cloud.git`
4. **Testar**: `curl http://<IP_PUBLICO>/health`

O serviço sobe como `api-tarefas.service` (systemd) e reinicia sozinho em caso de falha ou reboot.

## Limpeza

```bash
az group delete --name rg-api-tarefas --yes --no-wait
```
