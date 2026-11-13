
import requests
import json

# Consulta de teste: Camaquã, lavouras temporárias, ano 2025
url = (
    "https://apisidra.ibge.gov.br/values/"
    "t/1612/n6/4303509/"
    "v/109,216,214,112,215/"
    "p/2025/c81/all"
)

print("Consultando a API SIDRA...")
print("Município: Camaquã")
print("Tabela: 1612")
print("Ano: 2025")

try:
    resposta = requests.get(url, timeout=60)
    resposta.raise_for_status()

    dados = resposta.json()

    if not isinstance(dados, list) or len(dados) < 2:
        print("A API não retornou registros suficientes.")
        print(json.dumps(dados, ensure_ascii=False, indent=2)[:3000])
    else:
        print("\nCONSULTA REALIZADA")
        print("Total de linhas recebidas:", len(dados) - 1)

        print("\nCOLUNAS RETORNADAS:")
        print(json.dumps(dados[0], ensure_ascii=False, indent=2))

        print("\nPRIMEIROS REGISTROS:")
        for registro in dados[1:9]:
            print(json.dumps(registro, ensure_ascii=False))

except requests.exceptions.RequestException as erro:
    print("\nERRO NA CONSULTA:")
    print(erro)

except Exception as erro:
    print("\nERRO AO PROCESSAR OS DADOS:")
    print(erro)
