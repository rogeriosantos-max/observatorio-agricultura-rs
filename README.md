# Observatório Territorial da Agricultura – Centro-Sul do Rio Grande do Sul

**Plataforma interativa de análise territorial da agricultura, agricultura familiar, pecuária, crédito rural e uso e cobertura do solo.**

Aplicação desenvolvida em Python e Streamlit, com foco na organização, visualização e análise de indicadores territoriais dos municípios do Centro-Sul do Rio Grande do Sul.

## 1. Objetivo

Disponibilizar informações territoriais e indicadores agropecuários em uma plataforma interativa, apoiando atividades de ensino, pesquisa, extensão, planejamento e gestão territorial.

## 2. Abrangência territorial

O Observatório contempla 21 municípios do Centro-Sul do Rio Grande do Sul, com visualização cartográfica e ferramentas de consulta e comparação municipal.

## 3. Funcionalidades

- Mapa interativo dos municípios da região.
- Painel de produção agrícola.
- Indicadores de agricultura familiar.
- Painel de pecuária.
- Consulta e análise de crédito rural.
- Análise de uso e cobertura do solo.
- Comparação entre municípios.
- Gráficos e indicadores territoriais.
- Exportação de dados para Excel e CSV.
- Geração de relatórios em PDF, incluindo relatório executivo regional.

## 4. Fontes de dados

O projeto utiliza bases e informações provenientes de fontes institucionais, incluindo:

- **IBGE:** Produção Agrícola Municipal (PAM), Pesquisa da Pecuária Municipal (PPM), Censo Agropecuário e informações territoriais.
- **Banco Central do Brasil:** Sistema de Operações do Crédito Rural e do Proagro (SICOR).
- **MapBiomas:** dados de uso e cobertura da terra.
- **Outras fontes institucionais:** informações complementares, conforme disponibilidade e documentação.

Os anos de referência, unidades, filtros e características de cada base devem ser considerados na interpretação dos indicadores.

## 5. Tecnologias utilizadas

- Python
- Streamlit
- Pandas
- NumPy
- Plotly
- GeoPandas
- geobr
- Folium
- Streamlit-Folium
- OpenPyXL
- ReportLab

## 6. Instalação e execução

### Requisitos

- Windows 10 ou 11, ou ambiente compatível com Python.
- Python 3.13 ou versão compatível com as dependências.
- Conexão com a internet para instalação das bibliotecas e obtenção de recursos cartográficos, quando necessários.

### Instalação no Windows

Abra o terminal na pasta do projeto e execute:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Executar o Observatório

```bat
python -m streamlit run app.py
```

O Streamlit disponibilizará o endereço local para acesso pelo navegador, normalmente:

`http://localhost:8501`

## 7. Estrutura do projeto

```text
observatorio_agricultura_rs/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── config/
├── data/
│   ├── raw/
│   └── processed/
├── outputs/
├── outputs_sicor/
├── scripts/
└── src/
```

## 8. Dados e reprodutibilidade

As bases processadas utilizadas pelo dashboard estão organizadas no diretório `data/processed/`, enquanto os arquivos complementares de saída estão organizados nos diretórios correspondentes.

As rotinas de preparação e consulta de dados estão disponíveis em `scripts/`.

A interpretação dos resultados deve considerar a fonte, o ano de referência, a metodologia, as unidades e os eventuais filtros aplicados a cada conjunto de dados.

## 9. Desenvolvimento

O Observatório é um projeto em evolução. Melhorias, correções e contribuições são bem-vindas, especialmente nas áreas de integração de bases oficiais, qualidade dos dados, indicadores territoriais, visualização e análise espacial.

## 10. Responsabilidade

Os indicadores apresentados devem ser interpretados considerando as características e limitações das respectivas fontes de dados. A disponibilização dos dados no Observatório não substitui a consulta às bases oficiais e à documentação metodológica de cada instituição.