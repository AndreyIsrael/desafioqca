from pathlib import Path

import pandas as pd

from coleta_ibge.texto import chave_ordenacao

PASTA_SAIDA = Path(__file__).resolve().parent.parent / "output"

COLUNAS = [
    "codigo_ibge",
    "municipio",
    "uf",
    "regiao",
    "prefeito",
    "gentilico",
    "populacao_estimada",
    "ano_populacao",
    "area_km2",
    "ano_area",
    "url_fonte",
    "data_coleta",
]
CAMPOS_PORTAL = ["prefeito", "gentilico", "populacao_estimada", "ano_populacao", "area_km2", "ano_area"]
COLUNAS_OCORRENCIAS = ["codigo_ibge", "municipio", "tipo", "detalhe"]


def converter_numero_br(serie: pd.Series) -> pd.Series:
    texto = serie.astype("string").str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(texto, errors="coerce")


def _ordenar_por_nome(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values("municipio", key=lambda s: s.map(chave_ordenacao)).reset_index(drop=True)


def montar_municipios(registros: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(registros, columns=COLUNAS)

    df["codigo_ibge"] = df["codigo_ibge"].astype("string")
    if not df["codigo_ibge"].str.fullmatch(r"\d{7}").all():
        raise ValueError("Há códigos IBGE fora do padrão de 7 dígitos")
    df = df.drop_duplicates(subset="codigo_ibge")

    for coluna in ["municipio", "uf", "regiao", "prefeito", "gentilico", "url_fonte"]:
        df[coluna] = df[coluna].astype("string").str.strip()

    df["populacao_estimada"] = converter_numero_br(df["populacao_estimada"]).astype("Int64")
    df["area_km2"] = converter_numero_br(df["area_km2"]).astype("Float64")
    for coluna in ["ano_populacao", "ano_area"]:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce").astype("Int64")

    return _ordenar_por_nome(df)


def listar_ausencias(df: pd.DataFrame, ignorar: set[str]) -> list[dict]:
    ausencias = []
    for linha in df[~df["codigo_ibge"].isin(ignorar)].itertuples(index=False):
        faltando = [campo for campo in CAMPOS_PORTAL if pd.isna(getattr(linha, campo))]
        if faltando:
            ausencias.append({
                "codigo_ibge": linha.codigo_ibge,
                "municipio": linha.municipio,
                "tipo": "dado_ausente",
                "detalhe": ", ".join(faltando),
            })
    return ausencias


def montar_pib(df_municipios: pd.DataFrame, pib: dict[str, dict]) -> pd.DataFrame:
    df = df_municipios[["codigo_ibge", "municipio"]].copy()
    df["pib_mil_reais"] = pd.to_numeric(
        df["codigo_ibge"].map(lambda c: pib.get(c, {}).get("pib_mil_reais")), errors="coerce"
    ).astype("Float64")
    df["ano_pib"] = pd.to_numeric(
        df["codigo_ibge"].map(lambda c: pib.get(c, {}).get("ano_pib")), errors="coerce"
    ).astype("Int64")
    return df


def exportar(
    uf: str,
    municipios: pd.DataFrame,
    resumo: dict,
    ocorrencias: list[dict],
    pib: pd.DataFrame,
) -> Path:
    PASTA_SAIDA.mkdir(exist_ok=True)
    caminho = PASTA_SAIDA / f"municipios_{uf.lower()}.xlsx"

    with pd.ExcelWriter(caminho, engine="openpyxl") as arquivo:
        municipios.to_excel(arquivo, sheet_name="municipios", index=False)
        pd.DataFrame(list(resumo.items()), columns=["item", "valor"]).to_excel(
            arquivo, sheet_name="resumo", index=False
        )
        pd.DataFrame(ocorrencias, columns=COLUNAS_OCORRENCIAS).to_excel(
            arquivo, sheet_name="ocorrencias", index=False
        )
        pib.to_excel(arquivo, sheet_name="pib", index=False)

        for aba in arquivo.sheets.values():
            for coluna in aba.columns:
                largura = max(len(str(celula.value or "")) for celula in coluna)
                aba.column_dimensions[coluna[0].column_letter].width = min(largura + 2, 60)

    return caminho
