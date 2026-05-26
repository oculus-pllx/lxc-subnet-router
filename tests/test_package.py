def test_package_exposes_version():
    import lxc_subnet_router

    assert lxc_subnet_router.__version__
