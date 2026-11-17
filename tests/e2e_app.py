"""Browser-test server with a synthetic HTTPS transport, isolated from user data."""

import time
from urllib.parse import unquote

import httpx
from remote_fixture import FakeConnection

import backend.devices as device_module
from backend.config import DATA
from backend.main import create_app


class FixtureStream(httpx.SyncByteStream):
    def __init__(self, content):
        self.content = content

    def __iter__(self):
        for offset in range(0, len(self.content), 16384):
            time.sleep(0.1)
            yield self.content[offset : offset + 16384]


def fixture_request(request):
    name = unquote(request.url.path.rsplit("/", 1)[-1])
    content = f"fixture-{name}".encode() * 8192
    offset = int(request.headers.get("range", "bytes=0-").split("=")[1].split("-")[0])
    headers = {"ETag": '"fixture-v1"'}
    if offset:
        headers["Content-Range"] = f"bytes {offset}-{len(content) - 1}/{len(content)}"
    return httpx.Response(206 if offset else 200, headers=headers, stream=FixtureStream(content[offset:]))


app = create_app()
http = app.state.acquisition.http
http.client.close()
http.client = httpx.Client(transport=httpx.MockTransport(fixture_request))


def fixture_only(url):
    if not url.startswith("https://fixtures.example/"):
        raise ValueError("Browser tests only use synthetic fixture downloads")


http.check = fixture_only


# SSH/SFTP tests use an isolated local protocol double and never contact a Raspberry.

remote = FakeConnection(DATA / "ssh-fixture")


def synthetic_device(config):
    if config["host"] != "test-pi.invalid":
        raise ValueError("E2E SSH only permits the synthetic test device")
    return remote


def synthetic_probe(host, port):
    synthetic_device({"host": host})
    return {"fingerprint": "SHA256:" + "A" * 43, "previously_trusted": True}


app.state.devices.connect = synthetic_device
device_module.probe = synthetic_probe
device_module.trust = lambda host, port, expected: synthetic_probe(host, port)
