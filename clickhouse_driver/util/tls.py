"""Certificate hostname matching for ``tls_sni_override``.

When the SNI differs from the name the certificate must match, OpenSSL's
built-in hostname check can't be used, because Python passes it the SNI. The
connection checks the certificate itself after the handshake, with this
function.

Adapted from CPython 3.10's ``ssl.match_hostname``, ``_dnsname_match``,
``_inet_paton`` and ``_ipaddress_match`` (Python Software Foundation License).
``ssl.match_hostname`` is deprecated and was removed in Python 3.12, so it is
copied here instead of imported. One change from CPython: the subject
commonName fallback is dropped, because with ``check_hostname`` on Python sets
``hostname_checks_common_name = False``, so upstream's path never trusts it
either.
"""
import socket
from ssl import SSL_ERROR_SSL, SSLCertVerificationError


def _verify_error(message):
    # Set errno and strerror the way OpenSSL-raised errors do:
    # Connection._format_connection_error builds its message from strerror.
    return SSLCertVerificationError(
        SSL_ERROR_SSL, 'certificate verify failed: ' + message)


def _dnsname_match(dn, hostname):
    """Matching according to RFC 6125, section 6.4.3.

    - Hostnames are compared lower case.
    - Partial wildcards, multiple wildcards, a sole wildcard, and wildcards
      outside the left-most label are not supported.
    - A wildcard must match at least one character, and only one label.
    """
    if not dn:
        return False

    wildcards = dn.count('*')
    if not wildcards:
        return dn.lower() == hostname.lower()

    if wildcards > 1:
        raise _verify_error(
            'too many wildcards in certificate DNS name: {!r}.'.format(dn))

    dn_leftmost, sep, dn_remainder = dn.partition('.')

    if '*' in dn_remainder:
        raise _verify_error(
            'wildcard can only be present in the leftmost label: '
            '{!r}.'.format(dn))

    if not sep:
        raise _verify_error(
            'sole wildcard without additional labels is not supported: '
            '{!r}.'.format(dn))

    if dn_leftmost != '*':
        raise _verify_error(
            'partial wildcards in leftmost label are not supported: '
            '{!r}.'.format(dn))

    hostname_leftmost, sep, hostname_remainder = hostname.partition('.')
    if not hostname_leftmost or not sep:
        return False
    return dn_remainder.lower() == hostname_remainder.lower()


def _inet_paton(ipname):
    """Convert an IPv4 or IPv6 address to packed binary form.

    Raises ValueError if ``ipname`` is not an IP address.
    """
    try:
        addr = socket.inet_aton(ipname)
    except OSError:
        pass
    else:
        if socket.inet_ntoa(addr) == ipname:
            return addr
        raise ValueError(
            '{!r} is not a quad-dotted IPv4 address.'.format(ipname))

    try:
        return socket.inet_pton(socket.AF_INET6, ipname)
    except OSError:
        raise ValueError('{!r} is neither an IPv4 nor an IP6 '
                         'address.'.format(ipname))
    except AttributeError:
        pass

    raise ValueError('{!r} is not an IPv4 address.'.format(ipname))


def _ipaddress_match(cert_ipaddress, host_ip):
    # OpenSSL may add a trailing newline to a subjectAltName's IP address.
    return _inet_paton(cert_ipaddress.rstrip()) == host_ip


def match_hostname(cert, hostname):
    """Check that ``cert`` (as returned by ``SSLSocket.getpeercert()``)
    matches ``hostname``.

    IP addresses are matched against IP subjectAltName entries, and other
    names against DNS entries. Raises ``ssl.SSLCertVerificationError`` on a
    mismatch, and returns nothing on success.
    """
    if not cert:
        raise _verify_error(
            'no peer certificate to match against {!r}'.format(hostname))
    try:
        host_ip = _inet_paton(hostname)
    except ValueError:
        host_ip = None

    for key, value in cert.get('subjectAltName', ()):
        if key == 'DNS':
            if host_ip is None and _dnsname_match(value, hostname):
                return
        elif key == 'IP Address':
            if host_ip is not None and _ipaddress_match(value, host_ip):
                return

    # Same wording as OpenSSL's own hostname check.
    raise _verify_error(
        'Hostname mismatch, certificate is not valid for {!r}'.format(
            hostname))
