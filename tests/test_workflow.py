"""Workflow state transition engine and activity audit persistence tests."""

from models.issue import Issue
from models.activity import Activity
from services.workflow_service import WorkflowService
from tests.conftest import login


def test_valid_full_lifecycle_as_admin(app, sample_data):
    admin = sample_data['admin']
    issue = sample_data['issue1']

    steps = ['triaging', 'assigned', 'in_progress', 'code_review', 'qa_verification', 'resolved', 'closed']
    for target in steps:
        ok, msg = WorkflowService.transition_issue(issue, target, admin)
        assert ok is True, f"Failed transitioning to {target}: {msg}"
        assert issue.status == target

    assert issue.resolved_at is not None
    # Verify activity log recorded all transitions
    status_events = Activity.query.filter_by(issue_id=issue.id, event_type=Activity.EVT_STATUS_CHANGED).all()
    assert len(status_events) == len(steps)


def test_invalid_transition_rejected(app, sample_data):
    admin = sample_data['admin']
    issue = sample_data['issue1']  # Currently 'reported'
    ok, msg = WorkflowService.transition_issue(issue, 'resolved', admin)
    assert ok is False
    assert issue.status == 'reported'


def test_role_restricted_transitions(app, sample_data):
    reporter = sample_data['reporter']
    dev = sample_data['dev']
    issue = sample_data['issue2']  # Currently 'assigned'

    # Reporter cannot start development work
    ok, _ = WorkflowService.transition_issue(issue, 'in_progress', reporter)
    assert ok is False

    # Developer CAN move assigned -> in_progress -> code_review -> qa_verification
    for target in ['in_progress', 'code_review', 'qa_verification']:
        ok, msg = WorkflowService.transition_issue(issue, target, dev)
        assert ok is True, msg

    # Developer CANNOT mark qa_verification -> resolved
    ok, _ = WorkflowService.transition_issue(issue, 'resolved', dev)
    assert ok is False

    # Reporter CAN verify fix (qa_verification -> resolved)
    ok, _ = WorkflowService.transition_issue(issue, 'resolved', reporter)
    assert ok is True
    assert issue.status == 'resolved'

    # Reporter CAN reopen resolved issue
    ok, _ = WorkflowService.transition_issue(issue, 'reopened', reporter)
    assert ok is True
    assert issue.status == 'reopened'
    assert issue.resolved_at is None


    # Developer CAN reopen resolved issue? No, reporter reopens it.
    # Developer CAN transition reopened -> in_progress
    ok, msg = WorkflowService.transition_issue(issue, 'in_progress', dev)
    assert ok is True, msg
    assert issue.status == 'in_progress'


def test_developer_can_reject_code_review_to_in_progress(app, sample_data):
    """Developer can reject/request changes on code_review and move it back to in_progress."""
    dev = sample_data['dev']
    issue = sample_data['issue2']  # Currently 'assigned'

    # Move assigned -> in_progress -> code_review
    ok, _ = WorkflowService.transition_issue(issue, 'in_progress', dev)
    assert ok is True
    ok, _ = WorkflowService.transition_issue(issue, 'code_review', dev)
    assert ok is True
    assert issue.status == 'code_review'

    # Developer moves code_review back to in_progress (e.g., changes requested)
    ok, msg = WorkflowService.transition_issue(issue, 'in_progress', dev, notes='Review rejected: fix unit tests')
    assert ok is True, msg
    assert issue.status == 'in_progress'


def test_developer_restricted_transitions(app, sample_data):
    """Developer cannot perform unauthorized state transitions."""
    dev = sample_data['dev']
    issue1 = sample_data['issue1']  # 'reported'
    issue2 = sample_data['issue2']  # 'assigned'

    # Developer cannot triage reported issues
    ok, _ = WorkflowService.transition_issue(issue1, 'triaging', dev)
    assert ok is False

    # Developer cannot close assigned issues
    ok, _ = WorkflowService.transition_issue(issue2, 'closed', dev)
    assert ok is False

    # Developer cannot jump assigned -> resolved
    ok, _ = WorkflowService.transition_issue(issue2, 'resolved', dev)
    assert ok is False


def test_reporter_restricted_transitions(app, sample_data):
    """Reporter cannot perform developer or admin state transitions."""
    reporter = sample_data['reporter']
    issue2 = sample_data['issue2']  # 'assigned'

    # Reporter cannot start work
    ok, _ = WorkflowService.transition_issue(issue2, 'in_progress', reporter)
    assert ok is False

    # Reporter cannot close assigned issue
    ok, _ = WorkflowService.transition_issue(issue2, 'closed', reporter)
    assert ok is False


def test_api_transition_endpoint_validation(client, sample_data):
    """API transition endpoint enforces authentication, authorization, and state rules."""
    login(client, 'dev@test.dev')

    # Valid transition via API: assigned -> in_progress
    res = client.post('/api/v1/issues/CORE-2/transition', json={'target_status': 'in_progress'})
    assert res.status_code == 200
    data = res.get_json()
    assert data['success'] is True
    assert data['new_status'] == 'in_progress'

    # Invalid status name
    res = client.post('/api/v1/issues/CORE-2/transition', json={'target_status': 'invalid_status_xyz'})
    assert res.status_code == 400
    assert 'Invalid status' in res.get_json()['error']

    # Invalid transition (in_progress -> closed not allowed for developer)
    res = client.post('/api/v1/issues/CORE-2/transition', json={'target_status': 'closed'})
    assert res.status_code == 400
    assert 'not permitted' in res.get_json()['error']

    # Transition to code_review and then reject back to in_progress via API
    res = client.post('/api/v1/issues/CORE-2/transition', json={'target_status': 'code_review'})
    assert res.status_code == 200
    res = client.post('/api/v1/issues/CORE-2/transition', json={'target_status': 'in_progress', 'notes': 'Changes requested'})
    assert res.status_code == 200
    assert res.get_json()['new_status'] == 'in_progress'


def test_http_transition_endpoint_enforces_rules(client, sample_data):
    login(client, 'reporter@test.dev')
    res = client.post('/issues/CORE-2/transition', data={'target_status': 'in_progress'}, follow_redirects=True)
    assert res.status_code == 200
    assert b'not permitted' in res.data
    issue = Issue.query.filter_by(issue_key='CORE-2').first()
    assert issue.status == 'assigned'
