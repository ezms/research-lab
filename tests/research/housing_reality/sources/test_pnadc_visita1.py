import zipfile
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from lab.research.housing_reality.sources._utils import _is_valid_zip
from lab.research.housing_reality.sources.pnadc_visita1 import (
    PNADCVisita1DataSource,
    _fwf_params,
    _to_snake,
)


class TestToSnake:
    def test_plain_description(self):
        assert _to_snake("Tipo de domicílio") == "tipo_de_domicilio"

    def test_strips_accents(self):
        assert _to_snake("Número de cômodos") == "numero_de_comodos"

    def test_collapses_spaces_and_special(self):
        assert _to_snake("Condição no domicílio") == "condicao_no_domicilio"

    def test_empty_string(self):
        assert _to_snake("") == ""

    def test_float_nan(self):
        assert _to_snake(float("nan")) == ""


class TestFwfParams:
    def _layout(self, rows: list) -> pd.DataFrame:
        return pd.DataFrame(
            rows,
            columns=["variable", "description", "start", "end", "length", "decimals", "type"],
        )

    def test_colspecs_are_zero_indexed(self):
        layout = self._layout([["UF", "UF", "6", "7", "2", "", "C"]])
        colspecs, _, _ = _fwf_params(layout)
        assert colspecs == [(5, 7)]

    def test_uf_excluded_from_dtypes(self):
        layout = self._layout([["UF", "UF", "6", "7", "2", "", "C"]])
        _, _, dtypes = _fwf_params(layout)
        assert "UF" not in dtypes

    def test_numeric_large_becomes_float64(self):
        layout = self._layout([["VD5007", "Renda", "659", "666", "8", "", "N"]])
        _, _, dtypes = _fwf_params(layout)
        assert dtypes["VD5007"] == "Float64"

    def test_numeric_small_becomes_int8(self):
        layout = self._layout([["V2001", "Pessoas", "88", "89", "2", "", "N"]])
        _, _, dtypes = _fwf_params(layout)
        assert dtypes["V2001"] == "Int8"

    def test_char_length_1_becomes_int8(self):
        layout = self._layout([["V1022", "Situação", "32", "32", "1", "", "C"]])
        _, _, dtypes = _fwf_params(layout)
        assert dtypes["V1022"] == "Int8"

    def test_weight_length_15_becomes_float64(self):
        layout = self._layout([["V1032", "Peso", "58", "72", "15", "", "N"]])
        _, _, dtypes = _fwf_params(layout)
        assert dtypes["V1032"] == "Float64"


class TestIsValidZip:
    def test_valid_zip_returns_true(self, tmp_path: Path):
        path = tmp_path / "ok.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("file.txt", "content")
        assert _is_valid_zip(path) is True

    def test_truncated_returns_false(self, tmp_path: Path):
        path = tmp_path / "bad.zip"
        path.write_bytes(b"PK\x03\x04truncated")
        assert _is_valid_zip(path) is False

    def test_empty_returns_false(self, tmp_path: Path):
        path = tmp_path / "empty.zip"
        path.write_bytes(b"")
        assert _is_valid_zip(path) is False


class TestPNADCVisita1DataSourceParse:
    def _make_fwf_line(self, uf_code: str, age: str = "025") -> str:
        line = [" "] * 700
        for i, c in enumerate("2025"):
            line[i] = c
        line[5] = uf_code[0]
        line[6] = uf_code[1]
        line[31] = "1"
        line[32] = "1"
        for i, c in enumerate("  1234.5678900"):
            line[57 + i] = c
        line[87] = " "
        line[88] = "3"
        line[89] = "0"
        line[90] = "1"
        line[91] = "0"
        line[92] = "1"
        line[93] = "1"
        for i, c in enumerate(age):
            line[102 + i] = c
        line[105] = "1"
        return "".join(line)

    def _setup_zip(self, tmp_path: Path, lines: list[str]) -> None:
        import lab.research.housing_reality.sources.pnadc_visita1 as mod
        zip_name = "PNADC_2025_visita1_test.zip"
        zip_path = tmp_path / "pnadc" / "2025" / zip_name
        zip_path.parent.mkdir(parents=True)
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("PNADC_2025.txt", "\n".join(lines) + "\n")
        return zip_name

    def test_collect_splits_by_uf(self, tmp_path: Path, monkeypatch):
        import lab.research.housing_reality.sources.pnadc_visita1 as mod
        from lab.research.housing_reality.params import HousingRealityParams
        zip_name = self._setup_zip(tmp_path, [
            self._make_fwf_line("12"),
            self._make_fwf_line("11"),
            self._make_fwf_line("12"),
        ])
        monkeypatch.setattr(mod, "_find_zip_filename", lambda year: zip_name)

        result = PNADCVisita1DataSource(tmp_path).collect(HousingRealityParams())

        assert "AC" in result
        assert "RO" in result
        assert "moradores" in result["AC"]
        assert "moradores" in result["RO"]

    def test_collect_row_counts_match_input(self, tmp_path: Path, monkeypatch):
        import lab.research.housing_reality.sources.pnadc_visita1 as mod
        from lab.research.housing_reality.params import HousingRealityParams
        zip_name = self._setup_zip(tmp_path, [
            self._make_fwf_line("12"),
            self._make_fwf_line("12"),
            self._make_fwf_line("12"),
        ])
        monkeypatch.setattr(mod, "_find_zip_filename", lambda year: zip_name)

        result = PNADCVisita1DataSource(tmp_path).collect(HousingRealityParams())

        pf = pq.read_table(result["AC"]["moradores"])
        assert pf.num_rows == 3

    def test_collect_renames_columns(self, tmp_path: Path, monkeypatch):
        import lab.research.housing_reality.sources.pnadc_visita1 as mod
        from lab.research.housing_reality.params import HousingRealityParams
        zip_name = self._setup_zip(tmp_path, [self._make_fwf_line("12")])
        monkeypatch.setattr(mod, "_find_zip_filename", lambda year: zip_name)

        result = PNADCVisita1DataSource(tmp_path).collect(HousingRealityParams())

        df = pd.read_parquet(result["AC"]["moradores"])
        assert "uf" in df.columns
        assert "sexo" in df.columns
        assert "idade_na_data_de_referencia" in df.columns
        assert "V2007" not in df.columns


class TestPNADCVisita1DataSourceFindLocal:
    def test_find_local_returns_none_when_no_data(self, tmp_path):
        from lab.research.housing_reality.params import HousingRealityParams
        assert PNADCVisita1DataSource(tmp_path).find_local(HousingRealityParams()) is None

    def test_find_local_returns_results_per_uf(self, tmp_path):
        from lab.research.housing_reality.params import HousingRealityParams
        mapped = tmp_path / "pnadc" / "2025" / "mapped"
        mapped.mkdir(parents=True)
        for uf in ["AC", "SP"]:
            pd.DataFrame({"x": [1]}).to_parquet(mapped / f"{uf}_moradores.parquet")

        result = PNADCVisita1DataSource(tmp_path).find_local(HousingRealityParams())

        assert result is not None
        assert set(result.keys()) == {"AC", "SP"}
        assert "moradores" in result["AC"]

    def test_find_local_skips_files_without_underscore(self, tmp_path):
        from lab.research.housing_reality.params import HousingRealityParams
        mapped = tmp_path / "pnadc" / "2025" / "mapped"
        mapped.mkdir(parents=True)
        (mapped / "unexpected.parquet").write_bytes(b"")

        assert PNADCVisita1DataSource(tmp_path).find_local(HousingRealityParams()) is None
