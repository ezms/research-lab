"""Adapter: MercadoLivre Imóveis → property_inventory.

Requer ML_APP_ID e ML_SECRET no .env (registro gratuito em developers.mercadolibre.com.br).
Coleta listings da categoria MLB1459 (Imóveis) e particiona por UF.

Paginação: ML permite até offset 1000 com auth (50 resultados por página = 20 páginas).
"""
import logging
import os
import time
from pathlib import Path

import httpx
import pandas as pd

from lab.research.property_inventory.domain.ports import PropertyDataSource
from lab.research.property_inventory.params import PropertyInventoryParams

_log = logging.getLogger(__name__)

_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
_SEARCH_URL = "https://api.mercadolibre.com/sites/MLB/search"
_CATEGORY = "MLB1459"
_PAGE_SIZE = 50
_MAX_OFFSET = 1000  # limite da API com auth

# atributos ML → colunas do schema imovel
_ATTR_MAP = {
    "PROPERTY_TYPE":    "tipo_imovel",
    "BEDROOMS":         "n_quartos",
    "SUITES":           "n_suites",
    "FULL_BATHROOMS":   "n_banheiros",
    "HALF_BATHROOMS":   "n_lavabos",
    "TOTAL_AREA":       "area_total_m2",
    "COVERED_AREA":     "area_construida_m2",
    "LOT_AREA":         "area_terreno_m2",
    "GARAGE_SPACES":    "n_vagas_total",
    "GARAGE_TYPE":      "tipo_garagem",
    "FLOORS":           "n_andares",
    "FLOOR":            "andar",
    "OPERATION_TYPE":   "_negocio_raw",
    # amenidades booleanas
    "POOL":             "tem_piscina",
    "BALCONY":          "tem_varanda",
    "TERRACE":          "tem_terraco",
    "GARDEN":           "tem_jardim",
    "BARBECUE_GRILL":   "tem_churrasqueira",
    "GOURMET_SPACE":    "tem_area_gourmet",
    "PARTY_ROOM":       "tem_salao_festas",
    "GAME_ROOM":        "tem_salao_jogos",
    "GYM":              "tem_academia",
    "PLAYGROUND":       "tem_playground",
    "SAUNA":            "tem_sauna",
    "ELEVATOR":         "tem_elevador",
    "DOORMAN":          "tem_portaria",
    "ELECTRIC_GATE":    "tem_portao_eletrico",
    "CONDOMINIUM_GATE": "tem_portao",
    "SECURITY_CAMERA":  "tem_camera",
    "ALARM":            "tem_alarme",
    "AIR_CONDITIONING": "tem_ar_condicionado",
    "SOLAR_PANEL":      "tem_placa_solar",
    "GENERATOR":        "tem_gerador",
    "ARTESIAN_WELL":    "tem_poco_artesiano",
    "PET_AREA":         "tem_area_pet",
    "SPORTS_COURT":     "tipos_quadra",
}

_BOOL_ATTRS = {v for k, v in _ATTR_MAP.items() if v.startswith("tem_")}
_NEGOCIO_MAP = {"Venda": "venda", "Aluguel": "aluguel", "Temporada": "temporada"}


def _get_token(client: httpx.Client) -> str:
    app_id = os.environ.get("ML_APP_ID", "")
    secret = os.environ.get("ML_SECRET", "")
    if not app_id or not secret:
        raise EnvironmentError(
            "ML_APP_ID e ML_SECRET ausentes no .env. "
            "Registre em developers.mercadolibre.com.br para obter as credenciais."
        )
    resp = client.post(
        _TOKEN_URL,
        data={"grant_type": "client_credentials", "client_id": app_id, "client_secret": secret},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _parse_listing(item: dict) -> dict:
    row: dict = {
        "provedor": "mercadolivre",
        "url": item.get("permalink"),
        "id_externo": item.get("id"),
        "titulo_anuncio": item.get("title"),
    }

    addr = item.get("address") or item.get("location") or {}
    state_id = addr.get("state_id", "")
    row["uf"] = state_id.replace("BR-", "") if state_id else None
    row["cidade"] = addr.get("city_name") or addr.get("city", {}).get("name")
    row["bairro"] = addr.get("neighborhood_name") or addr.get("neighborhood", {}).get("name")
    row["cep"] = addr.get("zip_code")

    for attr in item.get("attributes", []):
        col = _ATTR_MAP.get(attr.get("id", ""))
        if not col:
            continue
        val = attr.get("value_name")
        if col in _BOOL_ATTRS:
            row[col] = val in ("Sim", "Yes", "true", "1") if val else None
        elif col == "_negocio_raw":
            row["negocio"] = _NEGOCIO_MAP.get(val)
        elif col in ("area_total_m2", "area_construida_m2", "area_terreno_m2", "valor_aluguel", "valor_venda"):
            try:
                row[col] = float(str(val).replace(",", ".")) if val else None
            except ValueError:
                row[col] = None
        elif col in ("n_quartos", "n_suites", "n_banheiros", "n_lavabos", "n_vagas_total", "n_andares", "andar"):
            try:
                row[col] = int(val) if val else None
            except ValueError:
                row[col] = None
        else:
            row[col] = val

    price = item.get("price")
    negocio = row.get("negocio")
    if price and negocio == "aluguel":
        row["valor_aluguel"] = float(price)
    elif price and negocio == "venda":
        row["valor_venda"] = float(price)

    row["descricao_texto"] = None  # ML search não retorna descrição; disponível via /items/{id}

    return row


class MLImoveisDataSource(PropertyDataSource):
    def __init__(self, work_dir: Path) -> None:
        self._base = work_dir / "property_inventory" / "ml_imoveis"

    def find_local(self, params: PropertyInventoryParams) -> dict[str, Path] | None:
        ufs = [uf.value for uf in params.ufs] if params.ufs else None
        results = {}
        if not self._base.exists():
            return None
        for f in self._base.glob("*.parquet"):
            if f.name.endswith(".tmp.parquet"):
                continue
            uf = f.stem
            if ufs is None or uf in ufs:
                results[uf] = f
        return results or None

    def collect(self, params: PropertyInventoryParams) -> dict[str, Path]:
        self._base.mkdir(parents=True, exist_ok=True)
        ufs_filter = {uf.value for uf in params.ufs} if params.ufs else None

        with httpx.Client(timeout=30) as client:
            token = _get_token(client)
            headers = {"Authorization": f"Bearer {token}"}

            rows: list[dict] = []
            offset = 0
            while offset < _MAX_OFFSET:
                resp = client.get(
                    _SEARCH_URL,
                    params={"category": _CATEGORY, "limit": _PAGE_SIZE, "offset": offset},
                    headers=headers,
                )
                if resp.status_code == 401:
                    token = _get_token(client)
                    headers["Authorization"] = f"Bearer {token}"
                    continue
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    break

                for item in results:
                    row = _parse_listing(item)
                    if ufs_filter and row.get("uf") not in ufs_filter:
                        continue
                    rows.append(row)

                paging = data.get("paging", {})
                total = paging.get("total", 0)
                offset += _PAGE_SIZE
                if offset >= total:
                    break

                time.sleep(0.3)  # respeita rate limit

            _log.info("coletados %d listings do ML", len(rows))

        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        return self._save_by_uf(df)

    def _save_by_uf(self, df: pd.DataFrame) -> dict[str, Path]:
        saved: dict[str, Path] = {}
        if df.empty:
            return saved
        for uf, group in df.groupby("uf"):
            if not uf:
                continue
            tmp = self._base / f"{uf}.tmp.parquet"
            out = self._base / f"{uf}.parquet"
            group.to_parquet(tmp, index=False)
            tmp.rename(out)
            saved[str(uf)] = out
            _log.info("salvo %s: %d listings", uf, len(group))
        return saved
