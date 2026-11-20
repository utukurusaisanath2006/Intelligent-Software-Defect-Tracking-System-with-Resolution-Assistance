"""Issue CRUD, search, filtering, pagination, comments, and attachments tests."""

import io
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
