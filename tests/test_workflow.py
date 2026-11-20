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


def test_http_transition_endpoint_enforces_rules(client, sample_data):
    login(client, 'reporter@test.dev')
    res = client.post('/issues/CORE-2/transition', data={'target_status': 'in_progress'}, follow_redirects=True)
    assert res.status_code == 200
    assert b'not permitted' in res.data
    issue = Issue.query.filter_by(issue_key='CORE-2').first()
    assert issue.status == 'assigned'
