"""Authentication and role dashboard routing tests."""

from tests.conftest import login


def test_login_page_loads(client):
    res = client.get('/auth/login')
    assert res.status_code == 200
    assert b'IntelliTrack' in res.data


def test_unauthenticated_redirect(client):
    res = client.get('/issues/', follow_redirects=False)
    assert res.status_code == 302
    assert '/auth/login' in res.headers['Location']


def test_login_invalid_credentials(client, sample_data):
    res = login(client, 'admin@test.dev', 'wrongpass')
    assert res.status_code == 200
    assert b'Invalid email address or password' in res.data


def test_login_inactive_user_blocked(client, sample_data):
    res = login(client, 'inactive@test.dev', 'secret123')
    assert res.status_code == 200
    assert b'deactivated' in res.data


def test_role_dashboards_load(client, sample_data):
    # Admin redirects to admin overview
    res = login(client, 'admin@test.dev')
    assert res.status_code == 200
    assert b'System Overview' in res.data
    client.get('/auth/logout')

    # Developer loads developer workspace
    res = login(client, 'dev@test.dev')
    assert res.status_code == 200
    assert b'Developer Workspace' in res.data
    client.get('/auth/logout')

    # Reporter loads reporter dashboard
    res = login(client, 'reporter@test.dev')
    assert res.status_code == 200
    assert b'Reporter Dashboard' in res.data


def test_logout_clears_session(client, sample_data):
    login(client, 'reporter@test.dev')
    res = client.get('/auth/logout', follow_redirects=True)
    assert res.status_code == 200
    assert b'logged out' in res.data
    protected = client.get('/dashboard', follow_redirects=False)
    assert protected.status_code == 302


def test_user_registration(client, sample_data):
    res = client.post('/auth/register', data={
        'first_name': 'New',
        'last_name': 'Tester',
        'username': 'newtester',
        'email': 'newtester@test.dev',
        'role': 'reporter',
        'password': 'password123',
        'confirm_password': 'password123',
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'registered' in res.data
