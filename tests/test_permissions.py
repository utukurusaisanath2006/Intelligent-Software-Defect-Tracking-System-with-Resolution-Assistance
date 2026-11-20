"""Role-based access control, project authorization, and admin safety tests."""

from models.user import User
from models.project import Project
from tests.conftest import login


def test_non_admin_blocked_from_admin_routes(client, sample_data):
    for email in ['reporter@test.dev', 'dev@test.dev']:
        login(client, email)
        for url in ['/admin/overview', '/admin/users', '/admin/projects', '/admin/analytics', '/admin/activity', '/admin/settings']:
            res = client.get(url)
            assert res.status_code == 403, f"{email} should be blocked from {url}"
        client.get('/auth/logout')


def test_project_level_idor_protection(client, sample_data):
    # Reporter belongs to CORE, NOT SEC
    login(client, 'reporter@test.dev')
    res = client.get('/issues/SEC-1')
    assert res.status_code == 403

    res_proj = client.get(f"/projects/{sample_data['proj2'].id}")
    assert res_proj.status_code == 403

    # Outsider belongs to NO projects
    client.get('/auth/logout')
    login(client, 'outsider@test.dev')
    assert client.get('/issues/CORE-1').status_code == 403
    assert client.get('/api/v1/issues/CORE-1').status_code == 403


def test_admin_can_manage_users_and_protect_last_admin(client, sample_data):
    login(client, 'admin@test.dev')
    admin_user = sample_data['admin']

    # Create a new user
    res = client.post('/admin/users/new', data={
        'first_name': 'Jane',
        'last_name': 'Doe',
        'username': 'janedoe',
        'email': 'jane@test.dev',
        'role': 'developer',
        'password': 'password123',
    }, follow_redirects=True)
    assert res.status_code == 200
    assert User.query.filter_by(email='jane@test.dev').first() is not None

    # Cannot deactivate self
    res_self = client.post(f'/admin/users/{admin_user.id}/toggle-active', follow_redirects=True)
    assert b'cannot deactivate your own account' in res_self.data
    assert User.query.get(admin_user.id).is_active is True

    # Cannot demote last active admin
    res_demote = client.post(f'/admin/users/{admin_user.id}/edit', data={
        'first_name': 'Admin',
        'last_name': 'User',
        'role': 'developer',
    }, follow_redirects=True)
    assert b'sole active administrator' in res_demote.data
    assert User.query.get(admin_user.id).role == User.ROLE_ADMIN


def test_admin_project_creation_and_archiving(client, sample_data):
    login(client, 'admin@test.dev')
    res = client.post('/admin/projects/new', data={
        'name': 'Billing Engine',
        'key': 'BILL',
        'description': 'Handles invoicing',
    }, follow_redirects=True)
    assert res.status_code == 200
    proj = Project.query.filter_by(key='BILL').first()
    assert proj is not None
    assert proj.status == Project.STATUS_ACTIVE

    res_arch = client.post(f'/admin/projects/{proj.id}/archive', follow_redirects=True)
    assert res_arch.status_code == 200
    assert Project.query.get(proj.id).status == Project.STATUS_ARCHIVED
