import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend import launch


@pytest.mark.parametrize(
    "configured,private,enabled,host",
    [
        (True, True, True, "0.0.0.0"),
        (False, True, True, "127.0.0.1"),
        (True, False, True, "127.0.0.1"),
        (True, True, False, "127.0.0.1"),
    ],
)
def test_launcher_never_exposes_unconfigured_or_public_server(
    monkeypatch, configured, private, enabled, host
):
    access = SimpleNamespace(
        config=lambda: {"port": 8123, "lan_enabled": enabled},
        configured=lambda: configured,
        interfaces=lambda: [{"private": private, "address": "192.168.44.20", "subnet": "192.168.44.0/24"}],
    )
    monkeypatch.setattr(launch, "Access", lambda data: access)
    monkeypatch.setattr("sys.argv", ["launch"])
    monkeypatch.setenv("RLM_LAN_ACTIVE", "0")
    run = Mock()
    monkeypatch.setattr("uvicorn.run", run)
    launch.main()
    assert run.call_args.kwargs["host"] == host
    assert run.call_args.kwargs["port"] == 8123
    assert run.call_args.kwargs["proxy_headers"] is False
    assert os.environ["RLM_LAN_ACTIVE"] == ("1" if host == "0.0.0.0" else "0")


@pytest.mark.parametrize("port", ["0", "80", "65536"])
def test_launcher_rejects_invalid_explicit_port(monkeypatch, port):
    monkeypatch.setattr(launch, "Access", lambda data: SimpleNamespace(config=lambda: {"port": 8000}))
    monkeypatch.setattr("sys.argv", ["launch", "--port", port])
    with pytest.raises(SystemExit, match="Porta consentita"):
        launch.main()
