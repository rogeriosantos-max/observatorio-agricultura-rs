
import base64
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from src.data import FILES


def admin_authenticated():
    """Verifica se o administrador está autenticado."""
    return st.session_state.get("admin_authenticated", False)


def admin_login():
    """Exibe o acesso restrito ao administrador."""
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False

    if st.session_state.admin_authenticated:
        st.success("Administrador autenticado.")
        if st.button("Sair do painel administrativo"):
            st.session_state.admin_authenticated = False
            st.rerun()
        return True

    st.subheader("Área administrativa")

    senha_configurada = st.secrets.get(
        "admin", {}
    ).get("password", "")

    if not senha_configurada:
        st.error("Senha administrativa não configurada.")
        return False

    senha_digitada = st.text_input(
        "Senha de administrador",
        type="password",
        key="senha_admin"
    )

    if st.button("Entrar no painel"):
        if hmac.compare_digest(
            senha_digitada, senha_configurada
        ):
            st.session_state.admin_authenticated = True
            st.rerun()
        else:
            st.error("Senha incorreta.")

    return st.session_state.admin_authenticated


def _github_config():
    """Lê as credenciais privadas do GitHub."""
    config = st.secrets.get("github", {})

    token = config.get("token", "")
    owner = config.get("owner", "")
    repo = config.get("repo", "")
    branch = config.get("branch", "main")

    if not all([token, owner, repo, branch]):
        raise ValueError(
            "Configuração do GitHub incompleta no secrets.toml."
        )

    return token, owner, repo, branch


def _github_request(method, path, payload=None):
    """Executa uma chamada autenticada à API do GitHub."""
    token, owner, repo, branch = _github_config()

    url = (
        "https://api.github.com/repos/"
        + urllib.parse.quote(owner, safe="")
        + "/"
        + urllib.parse.quote(repo, safe="")
        + "/contents/"
        + urllib.parse.quote(path, safe="/")
    )

    if method == "GET":
        url += "?" + urllib.parse.urlencode({"ref": branch})

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Observatorio-Agricultura-RS"
    }

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method
    )

    try:
        with urllib.request.urlopen(
            request, timeout=40
        ) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:
        detail = error.read().decode(
            "utf-8", errors="replace"
        )
        if error.code == 404:
            return None

        raise RuntimeError(
            f"GitHub retornou erro {error.code}: {detail}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Falha de conexão com o GitHub: {error}"
        ) from error


def validate_csv_upload(key, uploaded_file):
    """Valida o CSV antes de qualquer alteração no GitHub."""
    if key not in FILES:
        raise ValueError("Base de dados não reconhecida.")

    filename, columns = FILES[key]
    raw = uploaded_file.getvalue()

    if not raw:
        raise ValueError("O arquivo enviado está vazio.")

    try:
        df = pd.read_csv(
            BytesIO(raw),
            sep=None,
            engine="python",
            dtype={"codigo_ibge": str},
            encoding="utf-8-sig",
           
        )
    except Exception as error:
        raise ValueError(
            f"Não foi possível ler o CSV: {error}"
        ) from error

    missing = [
        column for column in columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            "Colunas obrigatórias ausentes: "
            + ", ".join(missing)
        )

    if df.empty:
        raise ValueError("O CSV não possui registros.")

    return df[columns].copy(), filename


def publish_csv_to_github(key, uploaded_file):
    """Faz backup e atualiza o CSV no GitHub."""
    df, filename = validate_csv_upload(
        key, uploaded_file
    )

    separator = ";" if key in ("agricola", "pecuaria") else ","

    csv_text = df.to_csv(
        index=False,
        sep=separator
    )
    new_content = csv_text.encode("utf-8-sig")

    original_path = f"data/processed/{filename}"

    # Recupera a versão atual do arquivo.
    current = _github_request(
        "GET", original_path
    )

    if current is None:
        raise RuntimeError(
            "O CSV original não foi encontrado no GitHub. "
            "Nenhuma alteração foi realizada."
        )

    if not current.get("content"):
        raise RuntimeError(
            "O GitHub não disponibilizou o conteúdo do CSV "
            "para criar a cópia de segurança."
        )

    old_content = base64.b64decode(
        current["content"]
    )

    # Cria cópia de segurança antes da substituição.
    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S_%f")

    backup_name = (
        Path(filename).stem
        + "_"
        + timestamp
        + "_backup.csv"
    )

    backup_path = f"data/backups/{backup_name}"

    backup_payload = {
        "message": (
            f"Backup de segurança antes da atualização de {filename}"
        ),
        "content": base64.b64encode(
            old_content
        ).decode("ascii"),
        "branch": _github_config()[3]
    }

    _github_request(
        "PUT", backup_path, backup_payload
    )

    # Atualiza o arquivo original usando o SHA atual.
    update_payload = {
        "message": f"Atualização administrativa: {filename}",
        "content": base64.b64encode(
            new_content
        ).decode("ascii"),
        "sha": current["sha"],
        "branch": _github_config()[3]
    }

    result = _github_request(
        "PUT", original_path, update_payload
    )

    if not result:
        raise RuntimeError(
            "Não foi possível confirmar a atualização no GitHub."
        )

    return len(df), backup_path, result["commit"]["sha"]

def test_github_connection():
    """Testa a leitura de um arquivo do repositório."""
    filename = FILES["agricola"][0]
    path = f"data/processed/{filename}"

    result = _github_request("GET", path)

    if result is None:
        raise RuntimeError(
            "Arquivo não encontrado no repositório: " + path
        )

    return result.get("name"), result.get("sha")
