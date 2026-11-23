"""Enterprise security hardening tests for IntelliTrack.

Verifies:
1. HTTP Security Response Headers (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy).
2. Session Cookie Hardening (HttpOnly, SameSite=Lax).
3. Sliding Session Expiration Lifetime configuration.
4. Attachment Download Security Headers (forced download, noopen, nosniff).
5. File Upload Magic Byte / Content Inspection (rejects disguised executables).
6. Sliding Window Login Rate Limiter (IP-based brute-force defense returning 429).
"""

import io
from flask import session
from models.attachment import Attachment
from routes.auth import login_limiter
from tests.conftest import login, TEST_PASSWORD_HASH


def test_http_security_headers_present_on_all_responses(client):
    """Verify that every HTTP response includes strict enterprise security headers."""
    res = client.get('/auth/login')
    assert res.status_code == 200

    # 1. Anti-MIME sniffing
    assert res.headers.get('X-Content-Type-Options') == 'nosniff'

    # 2. Clickjacking protection
    assert res.headers.get('X-Frame-Options') == 'SAMEORIGIN'

    # 3. Cross-Site Scripting protection filter
    assert res.headers.get('X-XSS-Protection') == '1; mode=block'

    # 4. Strict Referrer Policy
    assert res.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'

    # 5. Content Security Policy (CSP)
    csp = res.headers.get('Content-Security-Policy', '')
    assert "default-src 'self'" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "frame-ancestors 'self'" in csp


def test_session_cookie_security_configuration(app):
    """Verify session cookie flags for XSS mitigation and CSRF resistance."""
    assert app.config['SESSION_COOKIE_HTTPONLY'] is True
    assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'
    assert app.config['PERMANENT_SESSION_LIFETIME'].total_seconds() == 3600  # 60 minutes


def test_attachment_download_enforces_safe_headers(client, sample_data):
    """Verify that attachment downloads strictly enforce safe download headers."""
    login(client, 'reporter@test.dev')
    data = {
        'file': (io.BytesIO(b'timestamp=2026-11-23 level=INFO message=test_ok'), 'secure_audit.log')
    }
    upload_res = client.post('/issues/CORE-1/attachment', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert upload_res.status_code == 200

    att = Attachment.query.filter_by(original_filename='secure_audit.log').first()
    assert att is not None

    res = client.get(f'/issues/CORE-1/attachments/{att.id}/download')
    assert res.status_code == 200
    assert 'attachment; filename=secure_audit.log' in res.headers.get('Content-Disposition', '')
    assert res.headers.get('X-Content-Type-Options') == 'nosniff'
    assert res.headers.get('X-Download-Options') == 'noopen'


def test_disguised_executable_upload_blocked_by_magic_bytes(client, sample_data):
    """Verify that an executable payload disguised as an image is rejected by magic byte inspection."""
    login(client, 'reporter@test.dev')

    # Simulate a Windows PE executable (starts with MZ header) disguised as a PNG file
    fake_png_payload = b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00dangerous_payload'
    data = {
        'file': (io.BytesIO(fake_png_payload), 'malicious_imposter.png')
    }

    initial_count = Attachment.query.count()
    res = client.post('/issues/CORE-1/attachment', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert res.status_code == 200
    assert b'Upload rejected' in res.data or b'disallowed binary' in res.data
    # Attachment record must NOT have been saved
    assert Attachment.query.count() == initial_count


def test_legitimate_png_magic_bytes_accepted(client, sample_data):
    """Verify that a legitimate PNG file with valid magic bytes is successfully uploaded."""
    login(client, 'reporter@test.dev')

    # Valid PNG header signature
    real_png_payload = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    data = {
        'file': (io.BytesIO(real_png_payload), 'valid_screenshot.png')
    }

    initial_count = Attachment.query.count()
    res = client.post('/issues/CORE-1/attachment', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert res.status_code == 200
    assert b'valid_screenshot.png' in res.data
    assert Attachment.query.count() == initial_count + 1


def test_login_rate_limiter_blocks_brute_force_attack(client):
    """Verify that exceeding 5 failed login attempts triggers an HTTP 429 Too Many Requests response."""
    test_ip = '198.51.100.42'
    login_limiter.reset(test_ip)

    # First 5 attempts submit invalid password
    for i in range(5):
        res = client.post(
            '/auth/login',
            data={'email': 'admin@test.dev', 'password': f'wrong_pass_{i}'},
            headers={'X-Test-Rate-Limit': '1'},
            environ_overrides={'REMOTE_ADDR': test_ip}
        )
        assert res.status_code == 200  # Normal invalid credential response

    # 6th attempt should be blocked by rate limiter
    blocked_res = client.post(
        '/auth/login',
        data={'email': 'admin@test.dev', 'password': 'wrong_pass_6'},
        headers={'X-Test-Rate-Limit': '1'},
        environ_overrides={'REMOTE_ADDR': test_ip}
    )
    assert blocked_res.status_code == 429
    assert b'Too many login attempts' in blocked_res.data

    # Cleanup rate limiter
    login_limiter.reset(test_ip)
