"""Security utilities for URL validation, SSRF protection, and safe HTTP retrieval."""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Cloud metadata and link-local blocked networks
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # IPv4 loopback
    ipaddress.ip_network("10.0.0.0/8"),       # RFC 1918 private
    ipaddress.ip_network("172.16.0.0/12"),    # RFC 1918 private
    ipaddress.ip_network("192.168.0.0/16"),   # RFC 1918 private
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local / Cloud metadata (AWS/GCP/Azure)
    ipaddress.ip_network("100.64.0.0/10"),    # Carrier-grade NAT
    ipaddress.ip_network("0.0.0.0/8"),        # Current network
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]


def is_safe_external_url(url: str) -> tuple[bool, str]:
    """Validate that a URL is safe for server-side fetching, preventing SSRF attacks.

    Guarantees:
    - Scheme must be http or https
    - Host cannot be localhost or internal domain names
    - Resolved IP cannot belong to private, loopback, link-local, or cloud metadata ranges.

    Returns:
        tuple[bool, str]: (is_safe, rejection_reason)
    """
    if not url or not isinstance(url, str):
        return False, "URL is empty or invalid"

    try:
        parsed = urlparse(url.strip())
    except Exception as exc:
        return False, f"Malformed URL: {exc}"

    # 1. Scheme check
    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Unsupported URL scheme: {parsed.scheme}"

    # 2. Hostname check
    host = parsed.hostname
    if not host:
        return False, "Missing hostname in URL"

    host_lower = host.lower()
    if host_lower in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or host_lower.endswith(".local") or host_lower.endswith(".internal"):
        return False, f"Forbidden internal hostname: {host}"

    # 3. DNS Resolution and IP checks
    try:
        # Check if host is already a raw IP string
        ip_obj = ipaddress.ip_address(host_lower)
        ips = [ip_obj]
    except ValueError:
        # Resolve hostname to IPv4/IPv6 addresses
        try:
            addr_info = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            ips = [ipaddress.ip_address(info[4][0]) for info in addr_info]
        except socket.gaierror:
            return False, f"DNS resolution failed for host: {host}"
        except Exception as exc:
            return False, f"Resolution error: {exc}"

    for ip in ips:
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            return False, f"Target IP {ip} is within restricted/private network"
        for net in _BLOCKED_NETWORKS:
            if ip in net:
                return False, f"Target IP {ip} belongs to blocked subnet {net}"

    return True, ""


async def safe_fetch_image_bytes(
    image_url: str,
    max_bytes: int = 10_000_000,
    timeout: float = 6.0,
) -> bytes | None:
    """Safely fetch image content with SSRF filtering, timeout, and response size limits.

    Args:
        image_url: Target image URL.
        max_bytes: Maximum allowed payload size in bytes (default 10MB).
        timeout: Network timeout in seconds.

    Returns:
        Image bytes if successfully and safely fetched, else None.
    """
    is_safe, reason = is_safe_external_url(image_url)
    if not is_safe:
        logger.warning("SSRF Protection: Blocked fetch for unsafe URL '%s': %s", image_url[:60], reason)
        return None

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            # Stream response to enforce size limit before buffering into RAM
            async with client.stream("GET", image_url) as response:
                if response.status_code != 200:
                    logger.warning("Image download failed from %s (status %d)", image_url[:40], response.status_code)
                    return None

                # Check Content-Length header if available
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > max_bytes:
                    logger.warning("Image at %s exceeds maximum size of %d bytes", image_url[:40], max_bytes)
                    return None

                chunks = []
                total_bytes = 0
                async for chunk in response.aiter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        logger.warning("Image at %s exceeded maximum stream size limit (%d bytes)", image_url[:40], max_bytes)
                        return None
                    chunks.append(chunk)

                return b"".join(chunks)

    except httpx.TimeoutException:
        logger.warning("Timeout while fetching external image from %s", image_url[:40])
        return None
    except Exception as exc:
        logger.warning("Error fetching external image from %s: %s", image_url[:40], exc.__class__.__name__)
        return None
