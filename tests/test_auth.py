"""Authentication and role dashboard routing tests."""

from extensions import db
from models.user import User
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
    user = User.query.filter_by(username='newtester').first()
    assert user is not None
    assert user.role == User.ROLE_REPORTER


def test_public_registration_default_role(client, sample_data):
    """Public registration defaults to the reporter role without specifying role."""
    res = client.post('/auth/register', data={
        'first_name': 'Default',
        'last_name': 'User',
        'username': 'defaultuser',
        'email': 'default@test.dev',
        'password': 'password123',
        'confirm_password': 'password123',
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'registered' in res.data
    user = User.query.filter_by(username='defaultuser').first()
    assert user is not None
    assert user.role == User.ROLE_REPORTER


def test_attempted_developer_registration_ignored(client, sample_data):
    """Attempting to register with developer role must be ignored and assigned reporter."""
    res = client.post('/auth/register', data={
        'first_name': 'Sneaky',
        'last_name': 'Dev',
        'username': 'sneakydev',
        'email': 'sneakydev@test.dev',
        'role': 'developer',
        'password': 'password123',
        'confirm_password': 'password123',
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'registered' in res.data
    user = User.query.filter_by(username='sneakydev').first()
    assert user is not None
    assert user.role == User.ROLE_REPORTER


def test_attempted_admin_registration_ignored(client, sample_data):
    """Attempting to register with admin role must be ignored and assigned reporter."""
    res = client.post('/auth/register', data={
        'first_name': 'Sneaky',
        'last_name': 'Admin',
        'username': 'sneakyadmin',
        'email': 'sneakyadmin@test.dev',
        'role': 'admin',
        'password': 'password123',
        'confirm_password': 'password123',
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'registered' in res.data
    user = User.query.filter_by(username='sneakyadmin').first()
    assert user is not None
    assert user.role == User.ROLE_REPORTER


def test_unauthorized_user_cannot_modify_role(client, sample_data):
    """Non-admin user cannot access admin edit endpoint to change any user's role."""
    login(client, 'reporter@test.dev')
    rep = sample_data['reporter']
    res = client.post(f'/admin/users/{rep.id}/edit', data={
        'first_name': 'Hacked',
        'last_name': 'QA',
        'role': 'admin',
    }, follow_redirects=False)
    # admin blueprint before_request aborts with 403 for non-admins
    assert res.status_code == 403
    updated_rep = User.query.get(rep.id)
    assert updated_rep.role == User.ROLE_REPORTER


def test_admin_cannot_modify_own_role(client, sample_data):
    """Admin cannot change their own role, even when other admins exist."""
    admin1 = sample_data['admin']
    # Create a second admin to ensure the 'last active admin' check isn't what prevents it
    admin2 = User(
        username='admin2_t',
        email='admin2@test.dev',
        first_name='Admin2',
        last_name='User2',
        role=User.ROLE_ADMIN,
        is_active=True,
    )
    admin2.set_password('secret123')
    db.session.add(admin2)
    db.session.commit()

    login(client, 'admin@test.dev')
    res = client.post(f'/admin/users/{admin1.id}/edit', data={
        'first_name': 'Admin',
        'last_name': 'User',
        'role': 'developer',
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'cannot modify your own role' in res.data
    assert User.query.get(admin1.id).role == User.ROLE_ADMIN


def test_authorized_administrator_role_modification(client, sample_data):
    """Authorized admin can change another user's role."""
    login(client, 'admin@test.dev')
    rep = sample_data['reporter']
    assert rep.role == User.ROLE_REPORTER

    res = client.post(f'/admin/users/{rep.id}/edit', data={
        'first_name': 'QA',
        'last_name': 'Promoted',
        'role': 'developer',
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'updated successfully' in res.data
    updated_rep = User.query.get(rep.id)
    assert updated_rep.role == User.ROLE_DEVELOPER


def test_admin_role_change_rejects_invalid_role(client, sample_data):
    """Admin submitting an invalid role string leaves existing role untouched."""
    login(client, 'admin@test.dev')
    dev = sample_data['dev']
    assert dev.role == User.ROLE_DEVELOPER

    res = client.post(f'/admin/users/{dev.id}/edit', data={
        'first_name': 'Dev',
        'last_name': 'Engineer',
        'role': 'superadmin_invalid',
    }, follow_redirects=True)
    assert res.status_code == 200
    updated_dev = User.query.get(dev.id)
    assert updated_dev.role == User.ROLE_DEVELOPER


def test_password_hashing_security(app):
    """Verify that passwords are never stored in plaintext and password properties are enforced."""
    import pytest
    from werkzeug.security import check_password_hash

    # 1. Constructor automatic hashing
    user = User(
        username='hash_test_user',
        email='hashtest@test.dev',
        password='MySuperSecretPassword!123'
    )
    # Password column in DB must not be plaintext
    assert user.password_hash != 'MySuperSecretPassword!123'
    assert user.password_hash.startswith(('scrypt:', 'pbkdf2:'))
    assert user.check_password('MySuperSecretPassword!123') is True
    assert user.check_password('WrongPassword') is False

    # 2. Raw password must not be readable (write-only property)
    with pytest.raises(AttributeError):
        _ = user.password

    # 3. Setting password property triggers automatic re-hash
    old_hash = user.password_hash
    user.password = 'AnotherSecurePassword456'
    assert user.password_hash != old_hash
    assert user.password_hash != 'AnotherSecurePassword456'
    assert user.check_password('AnotherSecurePassword456') is True
    assert user.check_password('MySuperSecretPassword!123') is False


def test_seed_database_users_have_secure_hashes(app):
    """Verify database seeder loads users with hashed passwords and no plaintext credentials."""
    from seed import seed_database
    seed_database()

    for email, plain_pw in [
        ('admin@intellitrack.dev', 'admin123'),
        ('dev@intellitrack.dev', 'dev123'),
        ('sarah@intellitrack.dev', 'dev123'),
        ('reporter@intellitrack.dev', 'reporter123'),
    ]:
        user = User.query.filter_by(email=email).first()
        assert user is not None, f"User {email} not found"
        assert user.password_hash != plain_pw, f"User {email} has plaintext password stored"
        assert user.password_hash.startswith(('scrypt:', 'pbkdf2:'))
        assert user.check_password(plain_pw) is True


