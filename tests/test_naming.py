import pytest

from alien_creator.naming import build_sequence


def test_build_sequence_uses_trailing_number():
    assert build_sequence("PhantomHubs-Vpn-1", 3) == [
        "PhantomHubs-Vpn-1",
        "PhantomHubs-Vpn-2",
        "PhantomHubs-Vpn-3",
    ]


def test_build_sequence_increments_number_without_new_separator():
    assert build_sequence("PhantomExpress10GB-VIP1", 3) == [
        "PhantomExpress10GB-VIP1",
        "PhantomExpress10GB-VIP2",
        "PhantomExpress10GB-VIP3",
    ]


def test_build_sequence_can_start_from_any_number():
    assert build_sequence("Alien_29", 2) == ["Alien_29", "Alien_30"]


def test_build_sequence_requires_number():
    with pytest.raises(ValueError, match="انتها عدد"):
        build_sequence("Alien", 3)
