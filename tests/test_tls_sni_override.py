"""Tests for the Klaviyo fork's ``tls_sni_override`` connection option.

These run against a local TLS server, not ClickHouse. ``_create_socket``
returns once the TLS handshake and the certificate checks are done, before any
ClickHouse protocol bytes are sent, so the handshake is all they need.
"""
import socket
import ssl
import threading

import pytest
import trustme

from clickhouse_driver.connection import Connection

STICKY_SNI = 'l1-s1.sticky.db.example.test'


class TLSServer:
    """Accepts one TLS connection and records the SNI the client sent."""

    def __init__(self, ca, identities):
        self.received_sni = None
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ca.issue_cert(*identities).configure_cert(context)
        context.sni_callback = self._record_sni
        self._context = context
        self._listener = socket.create_server(('127.0.0.1', 0))
        self.port = self._listener.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _record_sni(self, ssl_socket, server_name, context):
        self.received_sni = server_name

    def _serve(self):
        try:
            conn, _ = self._listener.accept()
            with self._context.wrap_socket(conn, server_side=True) as tls:
                tls.recv(1)
        except OSError:
            # The client may reject the certificate, or never connect.
            pass

    def close(self):
        self._listener.close()
        self._thread.join(timeout=5)


@pytest.fixture
def ca():
    return trustme.CA()


@pytest.fixture
def ca_path(ca, tmp_path):
    path = tmp_path / 'ca.pem'
    ca.cert_pem.write_to_path(str(path))
    return str(path)


@pytest.fixture
def start_server(ca):
    servers = []

    def start(*identities, issuing_ca=None):
        server = TLSServer(issuing_ca or ca, identities)
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.close()


def connect(server, **kwargs):
    connection = Connection('127.0.0.1', port=server.port, secure=True,
                            **kwargs)
    return connection._create_socket('127.0.0.1', server.port)


def test_override_sends_sni_and_verifies_real_host(start_server, ca_path):
    server = start_server('*.example.test')

    sock = connect(server, ca_certs=ca_path,
                   server_hostname='db.example.test',
                   tls_sni_override=STICKY_SNI)
    sock.close()

    assert server.received_sni == STICKY_SNI


def test_override_rejects_cert_for_other_host(start_server, ca_path):
    server = start_server('other.example.test')

    with pytest.raises(ssl.SSLCertVerificationError) as excinfo:
        connect(server, ca_certs=ca_path,
                server_hostname='db.example.test',
                tls_sni_override=STICKY_SNI)

    # Connection._format_connection_error builds the NetworkError message
    # from strerror, so it must carry the reason.
    assert excinfo.value.strerror == (
        "certificate verify failed: Hostname mismatch, certificate is not "
        "valid for 'db.example.test'"
    )


def test_override_rejects_untrusted_ca(start_server, ca_path):
    server = start_server('*.example.test', issuing_ca=trustme.CA())

    with pytest.raises(ssl.SSLCertVerificationError):
        connect(server, ca_certs=ca_path,
                server_hostname='db.example.test',
                tls_sni_override=STICKY_SNI)


def test_override_matches_ip_san(start_server, ca_path):
    server = start_server('127.0.0.1')

    sock = connect(server, ca_certs=ca_path, tls_sni_override=STICKY_SNI)
    sock.close()

    assert server.received_sni == STICKY_SNI


def test_override_without_verify_skips_checks(start_server):
    server = start_server('other.example.test', issuing_ca=trustme.CA())

    sock = connect(server, verify=False, server_hostname='db.example.test',
                   tls_sni_override=STICKY_SNI)
    sock.close()

    assert server.received_sni == STICKY_SNI


def test_no_override_keeps_upstream_behavior(start_server, ca_path):
    server = start_server('db.example.test')

    sock = connect(server, ca_certs=ca_path,
                   server_hostname='db.example.test')
    sock.close()

    assert server.received_sni == 'db.example.test'
