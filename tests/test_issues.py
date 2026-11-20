"""Issue CRUD, search, filtering, pagination, comments, and attachments tests."""

import io
import os
from extensions import db
from models.issue import Issue
from models.comment import Comment
from models.attachment import Attachment
from tests.conftest import login


def test_create_issue_and_key_generation(client, sample_data):
    login(client, 'reporter@test.dev')
    proj1 = sample_data['proj1']
    res = client.post('/issues/new', data={
        'project_id': proj1.id,
        'title': 'API endpoint returns 500 error on malformed JSON',
        'description': 'Sending broken payload to REST endpoint crashes server.',
        'issue_type': 'bug',
        'severity': 'major',
        'priority': 'high',
        'component': 'REST API',
        'environment': 'Staging Linux',
        'steps_to_reproduce': '1. POST malformed JSON',
        'expected_result': 'HTTP 400 Bad Request',
        'actual_result': 'HTTP 500 Internal Server Error',
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b'CORE-3' in res.data
    created = Issue.query.filter_by(issue_key='CORE-3').first()
    assert created is not None
    assert created.category == 'backend_api'  # Auto-detected from keywords


def test_list_and_filter_issues(client, sample_data):
    login(client, 'reporter@test.dev')
    res = client.get('/issues/?severity=critical')
    assert res.status_code == 200
    assert b'CORE-1' in res.data
    assert b'CORE-2' not in res.data
    assert b'SEC-1' not in res.data  # No access to SEC project


def test_search_issues_via_list(client, sample_data):
    login(client, 'reporter@test.dev')
    res = client.get('/issues/?q=deadlock')
    assert res.status_code == 200
    assert b'CORE-1' in res.data
    assert b'CORE-2' not in res.data


def test_view_issue_detail_shows_suggestions(client, sample_data):
    login(client, 'dev@test.dev')
    res = client.get('/issues/CORE-1')
    assert res.status_code == 200
    assert b'Database deadlock on checkout transaction' in res.data
    assert b'Resolution Assistance' in res.data


def test_add_comment_persists(client, sample_data):
    login(client, 'dev@test.dev')
    res = client.post('/issues/CORE-1/comment', data={
        'body': 'Investigating lock contention in order_items table.'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'Investigating lock contention' in res.data
    assert Comment.query.count() == 1


def test_update_issue_root_cause(client, sample_data):
    login(client, 'dev@test.dev')
    res = client.post('/issues/CORE-2/update', data={
        'root_cause': 'Flexbox gap miscalculation',
        'resolution_notes': 'Updated CSS layout rule.',
    }, follow_redirects=True)
    assert res.status_code == 200
    updated = Issue.query.filter_by(issue_key='CORE-2').first()
    assert updated.root_cause == 'Flexbox gap miscalculation'
    assert updated.resolution_notes == 'Updated CSS layout rule.'


def test_upload_attachment(client, sample_data):
    login(client, 'reporter@test.dev')
    data = {
        'file': (io.BytesIO(b'error log trace line 1'), 'stacktrace.log')
    }
    res = client.post('/issues/CORE-1/attachment', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert res.status_code == 200
    assert b'stacktrace.log' in res.data
    assert Attachment.query.count() == 1


def test_authorized_download_attachment(client, app, sample_data):
    login(client, 'dev@test.dev')
    data = {'file': (io.BytesIO(b'critical diagnostic log content'), 'debug.log')}
    res_upload = client.post('/issues/CORE-1/attachment', data=data, content_type='multipart/form-data', follow_redirects=True)
    assert res_upload.status_code == 200
    att = Attachment.query.filter_by(original_filename='debug.log').first()
    assert att is not None

    res_down = client.get(f'/issues/CORE-1/attachments/{att.id}/download')
    assert res_down.status_code == 200
    assert res_down.data == b'critical diagnostic log content'
    assert 'attachment; filename=debug.log' in res_down.headers.get('Content-Disposition', '')


def test_unauthenticated_download_attachment(client, sample_data):
    login(client, 'reporter@test.dev')
    data = {'file': (io.BytesIO(b'auth required log'), 'auth_check.log')}
    client.post('/issues/CORE-1/attachment', data=data, content_type='multipart/form-data', follow_redirects=True)
    att = Attachment.query.filter_by(original_filename='auth_check.log').first()
    assert att is not None

    client.get('/auth/logout')

    res = client.get(f'/issues/CORE-1/attachments/{att.id}/download', follow_redirects=False)
    assert res.status_code == 302
    assert '/auth/login' in res.headers.get('Location', '')


def test_unauthorized_project_member_download_attachment(client, sample_data):
    login(client, 'reporter@test.dev')
    data = {'file': (io.BytesIO(b'secret project log'), 'confidential.log')}
    client.post('/issues/CORE-1/attachment', data=data, content_type='multipart/form-data', follow_redirects=True)
    att = Attachment.query.filter_by(original_filename='confidential.log').first()
    assert att is not None

    client.get('/auth/logout')
    login(client, 'outsider@test.dev')

    res = client.get(f'/issues/CORE-1/attachments/{att.id}/download')
    assert res.status_code == 403


def test_missing_attachment_download(client, sample_data):
    login(client, 'dev@test.dev')
    res = client.get('/issues/CORE-1/attachments/99999/download')
    assert res.status_code == 404

    res2 = client.get('/issues/NONEXISTENT-999/attachments/1/download')
    assert res2.status_code == 404

    ghost_att = Attachment(
        issue_id=sample_data['issue1'].id,
        uploader_id=sample_data['dev'].id,
        stored_filename='non_existent_file_on_disk.log',
        original_filename='ghost.log',
    )
    db.session.add(ghost_att)
    db.session.commit()

    res3 = client.get(f'/issues/CORE-1/attachments/{ghost_att.id}/download')
    assert res3.status_code == 404


def test_path_traversal_attachment_attempt(client, app, sample_data):
    login(client, 'dev@test.dev')
    malicious_att = Attachment(
        issue_id=sample_data['issue1'].id,
        uploader_id=sample_data['dev'].id,
        stored_filename='../../config.py',
        original_filename='evil.txt',
    )
    db.session.add(malicious_att)
    db.session.commit()

    res = client.get(f'/issues/CORE-1/attachments/{malicious_att.id}/download')
    assert res.status_code in [400, 403, 404]
    assert b'SECRET_KEY' not in res.data


def test_legacy_attachment_compatibility(client, app, sample_data):
    login(client, 'dev@test.dev')
    legacy_folder = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(legacy_folder, exist_ok=True)
    legacy_filename = 'legacy_test_file_123.log'
    legacy_path = os.path.join(legacy_folder, legacy_filename)
    with open(legacy_path, 'wb') as f:
        f.write(b'legacy file content preserved')

    legacy_att = Attachment(
        issue_id=sample_data['issue1'].id,
        uploader_id=sample_data['dev'].id,
        stored_filename=legacy_filename,
        original_filename='legacy_readme.log',
    )
    db.session.add(legacy_att)
    db.session.commit()

    res = client.get(f'/issues/CORE-1/attachments/{legacy_att.id}/download')
    assert res.status_code == 200
    assert res.data == b'legacy file content preserved'

    res_direct = client.get(f'/static/uploads/{legacy_filename}')
    assert res_direct.status_code == 404

    try:
        os.remove(legacy_path)
    except Exception:
        pass
