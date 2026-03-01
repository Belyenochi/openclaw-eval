import openclaw_edd.cli as cli


def test_cli_has_main():
    assert callable(cli.main)
