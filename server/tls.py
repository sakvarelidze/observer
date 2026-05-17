from __future__ import annotations

import asyncio
import ssl
from contextlib import suppress
from typing import Iterable, List

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

CONNECT_TIMEOUT = 6.0
SHUTDOWN_TIMEOUT = 0.6


def to_der_bytes(obj) -> bytes:
    """Accept bytes, ``cryptography`` or PyOpenSSL certs and return DER bytes."""
    if isinstance(obj, (bytes, bytearray, memoryview)):
        return bytes(obj)
    if isinstance(obj, x509.Certificate):
        return obj.public_bytes(serialization.Encoding.DER)
    try:  # pragma: no cover - optional dependency
        from OpenSSL.crypto import (
            X509 as OpenSSLX509,
            dump_certificate,
            FILETYPE_ASN1,
        )

        if isinstance(obj, OpenSSLX509):
            return dump_certificate(FILETYPE_ASN1, obj)
    except Exception:  # pragma: no cover - best effort import
        pass
    raise TypeError(f"Unsupported cert object type: {type(obj)!r}")


def parse_chain(der_list: Iterable[bytes]) -> List[x509.Certificate]:
    return [x509.load_der_x509_certificate(b, default_backend()) for b in der_list]


def is_ca(cert: x509.Certificate) -> bool:
    try:
        bc = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
        return bool(bc.ca)
    except Exception:
        return False


async def fetch_presented_chain(
    host: str,
    port: int,
    server_hostname: str,
    connect_timeout: float = CONNECT_TIMEOUT,
    shutdown_timeout: float = SHUTDOWN_TIMEOUT,
) -> List[x509.Certificate]:
    """Return the certificate chain presented by *host*:*port*.

    The chain is returned as a list of :class:`x509.Certificate` objects ordered as
    presented by the peer.  TLS verification is disabled so that self-signed chains
    can be retrieved.
    """

    unverified = ssl._create_unverified_context()
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(
            host,
            port,
            ssl=unverified,
            server_hostname=server_hostname,
        ),
        timeout=connect_timeout,
    )
    try:
        ssl_obj = writer.get_extra_info("ssl_object")
        chain_objs = None
        for attr in ("get_verified_chain", "getpeercertchain", "get_peer_cert_chain"):
            fn = getattr(ssl_obj, attr, None)
            if callable(fn):
                with suppress(Exception):
                    chain_objs = fn()
                    if chain_objs:
                        break
        if not chain_objs:
            leaf_der = ssl_obj.getpeercert(binary_form=True)
            chain_objs = [leaf_der]
        chain_der = [to_der_bytes(x) for x in chain_objs]
    finally:
        writer.close()
        with suppress(asyncio.TimeoutError, Exception):
            await asyncio.wait_for(writer.wait_closed(), timeout=shutdown_timeout)

    return parse_chain(chain_der)
