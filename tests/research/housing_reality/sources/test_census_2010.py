import zipfile
from pathlib import Path

import pandas as pd
import pytest

from lab.enums.uf import UF
from lab.research.housing_reality.params import HousingRealityParams
from lab.research.housing_reality.sources._utils import _is_valid_zip
from lab.research.housing_reality.sources.census_2010 import (
    Census2010DataSource,
    _fwf_params,
    _to_snake,
)


class TestToSnake:
    def test_description_with_colon(self):
        assert _to_snake("SITUAÇÃO DO DOMICÍLIO: 1- Urbana 2- Rural") == "situacao_do_domicilio"

    def test_description_with_category_no_colon(self):
        assert _to_snake("REGIÃO 1- Região norte (uf=11 a 17)") == "regiao"

    def test_plain_description(self):
        assert _to_snake("CÓDIGO DO MUNICÍPIO") == "codigo_do_municipio"

    def test_float_nan_returns_empty(self):
        assert _to_snake(float("nan")) == ""

    def test_empty_string_returns_empty(self):
        assert _to_snake("") == ""

    def test_none_returns_empty(self):
        assert _to_snake(None) == ""

    def test_en_dash_category_separator(self):
        result = _to_snake("VARIÁVEL 1– Categoria A 2– Categoria B")
        assert result == "variavel"

    def test_with_space_before_category_dash(self):
        result = _to_snake("SITUAÇÃO DO SETOR 1 - Área urbanizada 2 - Área rural")
        assert result == "situacao_do_setor"


class TestFwfParams:
    def _layout(self, rows: list) -> pd.DataFrame:
        return pd.DataFrame(
            rows, columns=["variable", "description", "start", "end", "length", "decimals", "type"]
        )

    def test_colspecs_are_zero_indexed(self):
        layout = self._layout([["V0001", "UF", "1", "2", "2", "", "A"]])
        colspecs, _, _ = _fwf_params(layout)
        assert colspecs == [(0, 2)]

    def test_multiple_colspecs(self):
        layout = self._layout([
            ["V0001", "UF",  "1", "2",  "2", "", "A"],
            ["V0002", "MUN", "3", "7",  "5", "", "A"],
        ])
        colspecs, _, _ = _fwf_params(layout)
        assert colspecs == [(0, 2), (2, 7)]

    def test_variable_names_preserved(self):
        layout = self._layout([
            ["V0001", "UF",  "1", "2", "2", "", "A"],
            ["V0002", "MUN", "3", "7", "5", "", "A"],
        ])
        _, names, _ = _fwf_params(layout)
        assert names == ["V0001", "V0002"]

    def test_dtype_int8_for_length_lte_2(self):
        layout = self._layout([["V0001", "UF", "1", "2", "2", "", "A"]])
        _, _, dtypes = _fwf_params(layout)
        assert dtypes["V0001"] == "Int8"

    def test_dtype_int16_for_length_3_to_4(self):
        layout = self._layout([["V0003", "VAR", "1", "4", "4", "", "N"]])
        _, _, dtypes = _fwf_params(layout)
        assert dtypes["V0003"] == "Int16"

    def test_dtype_int32_for_length_5_to_9(self):
        layout = self._layout([["V0005", "VAR", "1", "8", "8", "", "N"]])
        _, _, dtypes = _fwf_params(layout)
        assert dtypes["V0005"] == "Int32"

    def test_dtype_float64_for_decimal_column(self):
        layout = self._layout([["V0010", "PESO", "29", "44", "3", "13", "N"]])
        _, _, dtypes = _fwf_params(layout)
        assert dtypes["V0010"] == "Float64"


class TestIsValidZip:
    def test_valid_zip_returns_true(self, tmp_path: Path):
        path = tmp_path / "ok.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("file.txt", "content")
        assert _is_valid_zip(path) is True

    def test_truncated_file_returns_false(self, tmp_path: Path):
        path = tmp_path / "bad.zip"
        path.write_bytes(b"PK\x03\x04truncated garbage")
        assert _is_valid_zip(path) is False

    def test_empty_file_returns_false(self, tmp_path: Path):
        path = tmp_path / "empty.zip"
        path.write_bytes(b"")
        assert _is_valid_zip(path) is False


class TestFindLocal:
    def test_excludes_tmp_parquet(self, tmp_path: Path):
        mapped = tmp_path / "census_2010" / "AC" / "mapped"
        mapped.mkdir(parents=True)
        pd.DataFrame({"x": [1]}).to_parquet(mapped / "domicilios.parquet")
        (mapped / "pessoas.tmp.parquet").write_bytes(b"")  # half-written, must be ignored

        result = Census2010DataSource(tmp_path).find_local(HousingRealityParams(ufs=[UF.AC]))

        assert result == {"AC": {"domicilios": mapped / "domicilios.parquet"}}
