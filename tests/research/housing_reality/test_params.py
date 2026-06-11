import pytest
from pydantic import ValidationError

from lab.enums.uf import UF
from lab.research.housing_reality.params import HousingRealityParams


def test_default_has_no_ufs():
    assert HousingRealityParams().ufs is None


def test_single_uf():
    params = HousingRealityParams(ufs=[UF.AC])
    assert params.ufs == [UF.AC]


def test_multiple_ufs():
    params = HousingRealityParams(ufs=[UF.AC, UF.SP, UF.BA])
    assert len(params.ufs) == 3


def test_invalid_uf_raises():
    with pytest.raises(ValidationError):
        HousingRealityParams(ufs=["XX"])
