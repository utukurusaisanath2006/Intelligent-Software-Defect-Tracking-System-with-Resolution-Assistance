"""Release management CRUD, permissions, and issue association tests."""

from datetime import date
from extensions import db
from models.user import User
from models.project import Project, ProjectMembership
from models.release import Release
from models.issue import Issue
from tests.conftest import login


def test_list_releases_access(client, sample_data):
    """Admin and project members can view release list scoped to accessible projects."""
    login(client, 'admin@test.dev')
    res = client.get('/releases/')
    assert res.status_code == 200
    assert b'Release Management' in res.data
    client.get('/auth/logout')

    login(client, 'dev@test.dev')
    res = client.get('/releases/')
    assert res.status_code == 200
    assert b'Release Management' in res.data
    client.get('/auth/logout')

    login(client, 'reporter@test.dev')
    res = client.get('/releases/')
    assert res.status_code == 200


def test_create_release_and_role_permissions(client, sample_data):
    """Admin and developer can create releases; reporter cannot."""
    proj = sample_data['proj1']

    # 1. Reporter cannot create releases
    login(client, 'reporter@test.dev')
    res = client.post('/releases/new', data={
        'project_id': proj.id,
        'name': 'v1.0-reporter-attempt',
        'version': '1.0.0',
    })
    assert res.status_code == 403
    client.get('/auth/logout')

    # 2. Developer can create release in assigned project
    login(client, 'dev@test.dev')
    res = client.post('/releases/new', data={
        'project_id': proj.id,
        'name': 'v1.0 Milestone',
        'version': '1.0.0',
        'status': 'planning',
        'release_date': '2026-12-31',
        'description': 'Initial production milestone',
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'created successfully' in res.data

    release = Release.query.filter_by(name='v1.0 Milestone').first()
    assert release is not None
    assert release.version == '1.0.0'
    assert release.release_date == date(2026, 12, 31)
    assert release.project_id == proj.id


def test_create_release_validation_errors(client, sample_data):
    """Validation rejects empty name, invalid date, or unauthorized project."""
    proj = sample_data['proj1']
    login(client, 'admin@test.dev')

    # Empty name
    res = client.post('/releases/new', data={
        'project_id': proj.id,
        'name': '',
        'version': '1.0.0',
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'required' in res.data

    # Invalid date
    res = client.post('/releases/new', data={
        'project_id': proj.id,
        'name': 'Bad Date Release',
        'release_date': 'invalid-date',
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Invalid date format' in res.data


def test_view_release_and_idor_protection(client, sample_data):
    """Non-member cannot view release details (IDOR protection)."""
    proj = sample_data['proj1']
    release = Release(
        name='Secret Release',
        project_id=proj.id,
        status='planning'
    )
    db.session.add(release)
    db.session.commit()

    # Member can view
    login(client, 'dev@test.dev')
    res = client.get(f'/releases/{release.id}')
    assert res.status_code == 200
    assert b'Secret Release' in res.data
    client.get('/auth/logout')

    # Outsider blocked
    login(client, 'outsider@test.dev')
    res = client.get(f'/releases/{release.id}')
    assert res.status_code == 403


def test_edit_release(client, sample_data):
    """Admin/Developer can edit release details and status."""
    proj = sample_data['proj1']
    release = Release(
        name='Old Name',
        version='0.9',
        project_id=proj.id,
        status='planning'
    )
    db.session.add(release)
    db.session.commit()

    login(client, 'admin@test.dev')
    res = client.post(f'/releases/{release.id}/edit', data={
        'name': 'Updated Name',
        'version': '1.0',
        'status': 'in_progress',
        'release_date': '2026-11-30',
        'description': 'Updated description',
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'updated successfully' in res.data

    updated = Release.query.get(release.id)
    assert updated.name == 'Updated Name'
    assert updated.version == '1.0'
    assert updated.status == 'in_progress'
    assert updated.release_date == date(2026, 11, 30)


def test_update_release_status_quick_action(client, sample_data):
    """Quick status update action transitions release state."""
    proj = sample_data['proj1']
    release = Release(name='Quick Status Release', project_id=proj.id, status='planning')
    db.session.add(release)
    db.session.commit()

    login(client, 'dev@test.dev')
    res = client.post(f'/releases/{release.id}/status', data={'status': 'in_progress'}, follow_redirects=True)
    assert res.status_code == 200
    assert b'status updated to In Progress' in res.data
    assert Release.query.get(release.id).status == 'in_progress'


def test_add_and_remove_issue_from_release(client, sample_data):
    """Issue can be assigned and removed from a release."""
    proj = sample_data['proj1']
    issue = sample_data['issue1']  # in proj1
    release = Release(name='Sprint 1 Target', project_id=proj.id, status='planning')
    db.session.add(release)
    db.session.commit()

    login(client, 'dev@test.dev')

    # Add issue
    res = client.post(f'/releases/{release.id}/add-issue', data={'issue_id': issue.id}, follow_redirects=True)
    assert res.status_code == 200
    assert b'added to release' in res.data
    assert Issue.query.get(issue.id).release_id == release.id
    assert release.total_issues == 1

    # Remove issue
    res = client.post(f'/releases/{release.id}/remove-issue', data={'issue_id': issue.id}, follow_redirects=True)
    assert res.status_code == 200
    assert b'removed from release' in res.data
    assert Issue.query.get(issue.id).release_id is None
    assert release.total_issues == 0


def test_cross_project_issue_association_blocked(client, sample_data):
    """Cannot add issue from project A into release for project B."""
    proj1 = sample_data['proj1']
    proj2 = sample_data['proj2']
    issue_sec = sample_data['issue_sec']  # in proj2
    release1 = Release(name='Proj1 Release', project_id=proj1.id, status='planning')
    db.session.add(release1)
    db.session.commit()

    login(client, 'admin@test.dev')
    res = client.post(f'/releases/{release1.id}/add-issue', data={'issue_id': issue_sec.id}, follow_redirects=True)
    assert res.status_code == 200
    assert b'belongs to a different project' in res.data
    assert Issue.query.get(issue_sec.id).release_id is None


def test_safe_delete_release_preserves_issues(client, sample_data):
    """Deleting a release disassociates issues safely without deleting the issue records."""
    proj = sample_data['proj1']
    issue = sample_data['issue1']
    release = Release(name='Doomed Release', project_id=proj.id, status='planning')
    db.session.add(release)
    db.session.commit()

    issue.release_id = release.id
    db.session.commit()
    release_id = release.id
    issue_id = issue.id

    login(client, 'dev@test.dev')
    res = client.post(f'/releases/{release_id}/delete', follow_redirects=True)
    assert res.status_code == 200
    assert b'deleted safely' in res.data

    # Release is deleted
    assert Release.query.get(release_id) is None

    # Issue still exists and release_id is cleared
    retained_issue = Issue.query.get(issue_id)
    assert retained_issue is not None
    assert retained_issue.release_id is None


def test_issue_detail_page_assigns_release(client, sample_data):
    """Issue detail page allows assigning and removing release via assign_release route."""
    proj = sample_data['proj1']
    issue = sample_data['issue1']
    release = Release(name='Quick Assign Release', project_id=proj.id, status='planning')
    db.session.add(release)
    db.session.commit()

    login(client, 'dev@test.dev')
    res = client.post(f'/issues/{issue.issue_key}/assign-release', data={'release_id': release.id}, follow_redirects=True)
    assert res.status_code == 200
    assert b'assigned to release' in res.data
    assert Issue.query.get(issue.id).release_id == release.id

    # Unassign release
    res = client.post(f'/issues/{issue.issue_key}/assign-release', data={'release_id': ''}, follow_redirects=True)
    assert res.status_code == 200
    assert b'removed from release' in res.data
    assert Issue.query.get(issue.id).release_id is None
