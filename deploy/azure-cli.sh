#!/usr/bin/env bash
# Cria a infraestrutura na Azure (rode no Azure Cloud Shell ou com o az CLI logado).
set -euo pipefail

RG="rg-api-tarefas"
LOCATION="canadacentral"
VM="vm-gs"
SIZE="Standard_B2ats_v2"

# 0) (opcional) confira se o SKU esta disponivel na sua assinatura/regiao:
#    az vm list-skus -l "$LOCATION" --size "$SIZE" -o table
#    Se aparecer restricao, troque LOCATION (ex.: eastus2) ou SIZE.

# 1) Grupo de recursos
az group create --name "$RG" --location "$LOCATION"

# 2) VM Ubuntu 22.04 com disco de SO Premium SSD de 30 GiB e IP publico
az vm create \
  --resource-group "$RG" \
  --name "$VM" \
  --image Ubuntu2204 \
  --size "$SIZE" \
  --admin-username azureuser \
  --generate-ssh-keys \
  --storage-sku Premium_LRS \
  --os-disk-size-gb 30 \
  --public-ip-sku Standard

# 3) Libera a porta 80 (HTTP) no Network Security Group
az vm open-port --resource-group "$RG" --name "$VM" --port 80 --priority 900

# 4) IP publico da VM
az vm show -d --resource-group "$RG" --name "$VM" --query publicIps -o tsv

# Para apagar tudo depois da avaliacao (evita cobranca):
#   az group delete --name "$RG" --yes --no-wait
