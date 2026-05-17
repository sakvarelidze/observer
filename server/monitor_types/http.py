from __future__ import annotations
import httpx
import asyncio
import ssl
from datetime import datetime
from urllib.parse import urlparse

from cryptography import x509
from cryptography.hazmat.primitives import hashes

from server.tls import fetch_presented_chain

from .monitor_type import MonitorType
from .utils import exception_message, ssl_ctx_for_monitor


class HTTPMonitor(MonitorType):
    """Simple HTTP GET monitor."""

    name = "http"
    supports_conditions = True
    condition_variables = []
    

    def _is_status_accepted(self, status: int, accepted: list[str]) -> bool:
        """Return True if ``status`` is in ``accepted`` ranges."""
        for item in accepted:
            try:
                if "-" in item:
                    start, end = item.split("-", 1)
                    if int(start) <= status <= int(end):
                        return True
                else:
                    if status == int(item):
                        return True
            except ValueError:
                continue
        return False

    async def _cert_expiry_days(self, monitor, url: str) -> int | None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return None
        host = parsed.hostname
        port = parsed.port or 443
        try:
            ctx = ssl_ctx_for_monitor(monitor)
            if ctx is False:
                ctx = ssl._create_unverified_context()
            reader, writer = await asyncio.open_connection(
                host, port, ssl=ctx, server_hostname=host
            )
            ssl_obj = writer.get_extra_info("ssl_object")
            cert = ssl_obj.getpeercert() if ssl_obj else None
            writer.close()
            await writer.wait_closed()
            if not cert or "notAfter" not in cert:
                return None
            expiry = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
            return (expiry - datetime.utcnow()).days
        except Exception:
            return None

    async def check(self, monitor, heartbeat, server=None):
        url = getattr(monitor, "url", None)
        if not url:
            raise ValueError("Monitor must define a URL")
        timeout = getattr(monitor, "timeout", 10)
        try:
            method = getattr(monitor, "method", "GET").upper()
            headers = getattr(monitor, "headers", None)
            body = getattr(monitor, "body", None)
            auth = None
            if getattr(monitor, "basic_auth_user", None):
                auth = (
                    getattr(monitor, "basic_auth_user", ""),
                    getattr(monitor, "basic_auth_pass", ""),
                )

            proxies = None
            proxy = getattr(monitor, "proxy", None)
            if proxy and getattr(proxy, "active", True):
                proxy_auth = ""
                if getattr(proxy, "auth", False):
                    user = getattr(proxy, "username", "") or ""
                    pwd = getattr(proxy, "password", "") or ""
                    proxy_auth = f"{user}:{pwd}@"
                proxies = f"{proxy.protocol}://{proxy_auth}{proxy.host}:{proxy.port}"

            verify = ssl_ctx_for_monitor(monitor)
            try:
                async with httpx.AsyncClient(verify=verify, proxy=proxies) as client:
                    response = await client.request(
                        method,
                        url,
                        headers=headers,
                        content=body,
                        timeout=timeout,
                        auth=auth,
                    )
            except Exception as exc:
                fallback = await self._retry_presented_ca_with_pin(
                    monitor,
                    method,
                    url,
                    headers,
                    body,
                    timeout,
                    auth,
                    proxies,
                    exc,
                )
                if fallback is None:
                    raise
                response = fallback
            heartbeat.ping = response.elapsed.total_seconds() * 1000
            heartbeat.msg = f"HTTP {response.status_code}"
            accepted = getattr(monitor, "accepted_statuscodes", ["200-299"])
            if self._is_status_accepted(response.status_code, accepted):
                heartbeat.status = 1
            else:
                heartbeat.status = 0
            if getattr(monitor, "expiry_notification", False):
                heartbeat.cert_expire = await self._cert_expiry_days(monitor, url)
        except Exception as exc:
            heartbeat.status = 0
            heartbeat.msg = exception_message(exc)

    @staticmethod
    def _find_cert_verify_error(exc: Exception):
        seen: set[int] = set()
        current = exc
        while current and id(current) not in seen:
            if isinstance(current, ssl.SSLCertVerificationError):
                return current
            seen.add(id(current))
            current = (
                getattr(current, "__cause__", None)
                or getattr(current, "__context__", None)
            )
        return None

    async def _retry_presented_ca_with_pin(
        self,
        monitor,
        method: str,
        url: str,
        headers,
        body,
        timeout,
        auth,
        proxies,
        exc: Exception,
    ):
        if getattr(monitor, "tls_verify_mode", "") != "presented_ca":
            return None
        stored_fp = getattr(monitor, "custom_ca_sha256", None)
        if not stored_fp:
            return None
        if self._find_cert_verify_error(exc) is None:
            return None

        parsed = urlparse(url)
        if parsed.scheme != "https":
            return None

        host = parsed.hostname or getattr(monitor, "hostname", None)
        if not host:
            return None
        port = parsed.port or getattr(monitor, "port", None)
        if not port:
            port = 443

        try:
            chain = await fetch_presented_chain(
                host, port, getattr(monitor, "hostname", None) or host
            )
        except Exception:
            return None

        stored_fp = stored_fp.lower()
        match = any(
            cert.fingerprint(hashes.SHA256()).hex().lower() == stored_fp for cert in chain
        )
        if not match:
            pem_bundle = getattr(monitor, "custom_ca_pem", None)
            for cert in self._parse_pem_certificates(pem_bundle):
                if cert.fingerprint(hashes.SHA256()).hex().lower() == stored_fp:
                    match = True
                    break
        if not match:
            return None

        try:
            unverified_ctx = ssl._create_unverified_context()
            async with httpx.AsyncClient(verify=unverified_ctx, proxy=proxies) as client:
                return await client.request(
                    method,
                    url,
                    headers=headers,
                    content=body,
                    timeout=timeout,
                    auth=auth,
                )
        except Exception:
            return None

    @staticmethod
    def _parse_pem_certificates(pem: str | None):
        certs = []
        if not pem:
            return certs
        current: list[str] = []
        recording = False
        for line in pem.splitlines():
            stripped = line.strip()
            if stripped == "-----BEGIN CERTIFICATE-----":
                current = [line]
                recording = True
                continue
            if not recording:
                continue
            current.append(line)
            if stripped == "-----END CERTIFICATE-----":
                try:
                    certs.append(
                        x509.load_pem_x509_certificate("\n".join(current).encode("utf-8"))
                    )
                except Exception:
                    pass
                recording = False
        return certs
