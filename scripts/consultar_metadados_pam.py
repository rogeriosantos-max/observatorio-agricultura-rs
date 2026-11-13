
import requests
import json

for tabela in [1612, 1613]:

    url = (
        f"https://servicodados.ibge.gov.br/"
        f"api/v3/agregados/{tabela}/metadados"
    )

    print("\n" + "=" * 60)
    print(f"TABELA SIDRA {tabela}")
    print("=" * 60)

    resposta = requests.get(url, timeout=60)
    resposta.raise_for_status()

    dados = resposta.json()

    arquivo = f"metadados_pam_{tabela}.json"

    with open(arquivo, "w", encoding="utf-8") as f:
        json.dump(
            dados,
            f,
            ensure_ascii=False,
            indent=4
        )

    print(f"Arquivo salvo: {arquivo}")
    print(json.dumps(
        dados,
        ensure_ascii=False,
        indent=2
    )[:10000])
