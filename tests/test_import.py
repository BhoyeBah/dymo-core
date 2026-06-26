from dymo_saas_core import setup_saas_core


def test_package_exports_setup_saas_core() -> None:
    assert callable(setup_saas_core)

