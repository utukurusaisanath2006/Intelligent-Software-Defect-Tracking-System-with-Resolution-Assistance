"""CSRF Protection verification tests.

Verifies that all state-changing web forms and REST API endpoints strictly
enforce CSRF tokens and reject requests with missing or invalid tokens.
"""

import re
import pytest
from app import create_app
from extensions import db as _db
from models.user import User
from models.project import Project, ProjectMembership
from models.issue import Issue


@pytest.fixture(scope='function')
def csrf_app():
    """Create test application with CSRF protection explicitly ENABLED."""
    application = create_app('testing')
    application.config['WTF_CSRF_ENABLED'] = True
    with application.app_context():
        _db.create_all()

        # Seed sample data
        admin = User(username='admin_csrf', email='admin@csrf.dev', first_name='Admin', last_name='CSRF', role=User.ROLE_ADMIN, is_active=True)
        admin.set_password('secret123')

        dev = User(username='dev_csrf', email='dev@csrf.dev', first_name='Dev', last_name='CSRF', role=User.ROLE_DEVELOPER, is_active=True)
        dev.set_password('secret123')

        reporter = User(username='rep_csrf', email='reporter@csrf.dev', first_name='QA', last_name='CSRF', role=User.ROLE_REPORTER, is_active=True)
        reporter.set_password('secret123')

        _db.session.add_all([admin, dev, reporter])
        _db.session.flush()

        proj = Project(name='CSRF Project', key='CSRF', description='CSRF test project', status=Project.STATUS_ACTIVE)
        _db.session.add(proj)
        _db.session.flush()

        for u in [admin, dev, reporter]:
            _db.session.add(ProjectMembership(user_id=u.id, project_id=proj.id, role='member'))

        issue = Issue(
            issue_key='CSRF-1',
            title='Sample CSRF Test Defect',
            description='Testing CSRF security boundary',
            issue_type=Issue.TYPE_BUG,
            category='security',
            severity=Issue.SEV_MAJOR,
            priority=Issue.PRI_HIGH,
            status=Issue.STATUS_REPORTED,
            project_id=proj.id,
            reporter_id=reporter.id,
            assignee_id=dev.id,
        )
        _db.session.add(issue)
        _db.session.commit()

        yield application

        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope='function')
def csrf_client(csrf_app):
    """Test client bound to csrf_app."""
    return csrf_app.test_client()


def extract_form_token(html_text):
    """Extract CSRF token from rendered HTML form input."""
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html_text)
    if not match:
        match = re.search(r'value="([^"]+)"\s+name="csrf_token"', html_text)
    return match.group(1) if match else None


def extract_meta_token(html_text):
    """Extract CSRF token from meta header."""
    match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html_text)
    if not match:
        match = re.search(r'<meta\s+content="([^"]+)"\s+name="csrf-token"', html_text)
    return match.group(1) if match else None


def login_with_csrf(client, email='admin@csrf.dev', password='secret123'):
    """Helper to log in with proper CSRF token extraction."""
    res_get = client.get('/auth/login')
    token = extract_form_token(res_get.data.decode('utf-8'))
    assert token is not None, "Failed to extract CSRF token from login page"
    res_post = client.post('/auth/login', data={
        'email': email,
        'password': password,
        'csrf_token': token,
    }, follow_redirects=True)
    assert res_post.status_code == 200
    return token


# --- 1. Form CSRF Tests ---

def test_form_missing_csrf_token_rejected(csrf_client):
    """State-changing form submission without CSRF token must be rejected with HTTP 400."""
    res = client = csrf_client.post('/auth/login', data={
        'email': 'admin@csrf.dev',
        'password': 'secret123',
    })
    assert res.status_code == 400
    assert b'CSRF' in res.data or b'Bad Request' in res.data


def test_form_invalid_csrf_token_rejected(csrf_client):
    """State-changing form submission with invalid/tampered token must be rejected with HTTP 400."""
    # First get the page to establish session cookie
    csrf_client.get('/auth/login')
    res = csrf_client.post('/auth/login', data={
        'email': 'admin@csrf.dev',
        'password': 'secret123',
        'csrf_token': 'tampered_malicious_token_xyz',
    })
    assert res.status_code == 400


def test_form_valid_csrf_token_accepted(csrf_client):
    """Form submission with valid CSRF token must succeed."""
    res_get = csrf_client.get('/auth/login')
    token = extract_form_token(res_get.data.decode('utf-8'))
    assert token is not None

    res = csrf_client.post('/auth/login', data={
        'email': 'admin@csrf.dev',
        'password': 'secret123',
        'csrf_token': token,
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'System Overview' in res.data or b'Dashboard' in res.data


# --- 2. REST API CSRF Tests ---

def test_api_missing_csrf_token_rejected(csrf_client):
    """API state-changing POST without X-CSRFToken header must return HTTP 400 JSON error."""
    login_with_csrf(csrf_client, 'admin@csrf.dev')

    res = csrf_client.post('/api/v1/issues/CSRF-1/transition', json={
        'target_status': 'triaging',
    })
    assert res.status_code == 400
    assert res.is_json
    payload = res.get_json()
    assert payload['success'] is False
    assert 'CSRF' in payload['error']


def test_api_invalid_csrf_token_rejected(csrf_client):
    """API state-changing POST with invalid X-CSRFToken header must return HTTP 400 JSON error."""
    login_with_csrf(csrf_client, 'admin@csrf.dev')

    res = csrf_client.post('/api/v1/issues/CSRF-1/transition', json={
        'target_status': 'triaging',
    }, headers={
        'X-CSRFToken': 'tampered_token_9999',
    })
    assert res.status_code == 400
    assert res.is_json
    payload = res.get_json()
    assert payload['success'] is False
    assert 'CSRF' in payload['error']


def test_api_valid_csrf_token_accepted_transition(csrf_client):
    """API state-changing transition with valid X-CSRFToken header must succeed."""
    login_with_csrf(csrf_client, 'admin@csrf.dev')

    res_page = csrf_client.get('/issues/CSRF-1')
    meta_token = extract_meta_token(res_page.data.decode('utf-8'))
    assert meta_token is not None, "Failed to extract CSRF token from page meta tag"

    res = csrf_client.post('/api/v1/issues/CSRF-1/transition', json={
        'target_status': 'triaging',
        'notes': 'Triaged with verified CSRF token',
    }, headers={
        'X-CSRFToken': meta_token,
    })
    assert res.status_code == 200
    assert res.is_json
    payload = res.get_json()
    assert payload['success'] is True
    assert payload['new_status'] == 'triaging'


def test_api_classify_and_notifications_csrf_protection(csrf_client):
    """Verify that classify and notification endpoints enforce CSRF validation."""
    login_with_csrf(csrf_client, 'reporter@csrf.dev')

    # 1. Without token -> 400
    res_no_token = csrf_client.post('/api/v1/classify', json={
        'title': 'Memory leak in worker thread',
        'description': 'Out of memory exception',
    })
    assert res_no_token.status_code == 400

    res_notif_no_token = csrf_client.post('/api/v1/notifications/read-all')
    assert res_notif_no_token.status_code == 400

    # 2. With valid token -> 200
    res_page = csrf_client.get('/dashboard')
    meta_token = extract_meta_token(res_page.data.decode('utf-8'))
    assert meta_token is not None

    res_with_token = csrf_client.post('/api/v1/classify', json={
        'title': 'Memory leak in worker thread',
        'description': 'Out of memory exception',
    }, headers={'X-CSRFToken': meta_token})
    assert res_with_token.status_code == 200
    assert res_with_token.is_json
    assert res_with_token.get_json()['success'] is True

    res_notif_with_token = csrf_client.post('/api/v1/notifications/read-all', headers={'X-CSRFToken': meta_token})
    assert res_notif_with_token.status_code == 200
    assert res_notif_with_token.is_json
    assert res_notif_with_token.get_json()['success'] is True


# --- 3. Full Registration and Issue Management under CSRF Protection ---

def test_csrf_protected_registration_and_issue_creation(csrf_client):
    """Verify end-to-end registration, login, and issue creation with CSRF enabled."""
    # 1. Register
    res_reg_page = csrf_client.get('/auth/register')
    reg_token = extract_form_token(res_reg_page.data.decode('utf-8'))
    assert reg_token is not None

    res_reg = csrf_client.post('/auth/register', data={
        'username': 'new_reporter',
        'email': 'new_rep@csrf.dev',
        'first_name': 'New',
        'last_name': 'Reporter',
        'password': 'password123',
        'confirm_password': 'password123',
        'role': 'reporter',
        'csrf_token': reg_token,
    }, follow_redirects=True)
    assert res_reg.status_code == 200
    assert b'registered' in res_reg.data

    # 2. Login as newly registered user
    login_with_csrf(csrf_client, 'new_rep@csrf.dev', 'password123')

    # Grant membership to CSRF project for this new user so they can report an issue
    with csrf_client.application.app_context():
        u = User.query.filter_by(email='new_rep@csrf.dev').first()
        p = Project.query.filter_by(key='CSRF').first()
        _db.session.add(ProjectMembership(user_id=u.id, project_id=p.id, role='member'))
        _db.session.commit()
        proj_id = p.id

    # 3. Create Issue with valid CSRF token
    res_new_issue = csrf_client.get('/issues/new')
    issue_token = extract_form_token(res_new_issue.data.decode('utf-8'))
    assert issue_token is not None

    res_create = csrf_client.post('/issues/new', data={
        'project_id': proj_id,
        'title': 'Newly reported CSRF protected bug',
        'description': 'Verified with active token',
        'issue_type': 'bug',
        'severity': 'minor',
        'priority': 'medium',
        'csrf_token': issue_token,
    }, follow_redirects=True)
    assert res_create.status_code == 200
    assert b'CSRF-2' in res_create.data

    # 4. Attempt to create issue with tampered token -> MUST FAIL (400)
    res_fail = csrf_client.post('/issues/new', data={
        'project_id': proj_id,
        'title': 'Attacker forged bug',
        'csrf_token': 'fake_attacker_token',
    })
    assert res_fail.status_code == 400
