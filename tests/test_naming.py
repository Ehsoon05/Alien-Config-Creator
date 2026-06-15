import pytest

from alien_creator.naming import build_sequence


def test_build_sequence_uses_trailing_number():
    assert build_sequence("PhantomHubs-Vpn-1", 3) == [
        "PhantomHubs_Vpn_1",
        "PhantomHubs_Vpn_2",
        "PhantomHubs_Vpn_3",
    ]


def test_build_sequence_can_start_from_any_number():
    assert build_sequence("Alien_29", 2) == ["Alien_29", "Alien_30"]


def test_build_sequence_requires_number():
    with pytest.raises(ValueError, match="انتها عدد"):
        build_sequence("Alien", 3)

