"""REST API v1, Classification Service, Resolution Assistant, and Analytics tests."""

from services.classification_service import ClassificationService
from services.resolution_assistant import ResolutionAssistant
from services.analytics_service import AnalyticsService
from tests.conftest import login


def test_api_issues_and_search(client, sample_data):
    login(client, 'dev@test.dev')
    res = client.get('/api/v1/issues')
    assert res.status_code == 200
    payload = res.get_json()
    assert payload['success'] is True
    assert payload['total_items'] == 2  # Only CORE issues, not SEC

    search = client.get('/api/v1/search?q=deadlock')
    sdata = search.get_json()
    assert sdata['success'] is True
    assert len(sdata['data']) == 1
    assert sdata['data'][0]['issue_key'] == 'CORE-1'


def test_api_classify_endpoint(client, sample_data):
    login(client, 'reporter@test.dev')
    res = client.post('/api/v1/classify', json={
        'title': 'SQL injection vulnerability in login password auth',
        'description': 'Critical security breach allowing unauthorized access in production',
        'issue_type': 'bug',
    })
    assert res.status_code == 200
    data = res.get_json()['data']
    assert data['suggested_severity'] == 'critical'
    assert data['suggested_priority'] == 'urgent'
    assert data['suggested_category'] in ['security', 'authentication']


def test_api_suggestions_and_404(client, sample_data):
    login(client, 'dev@test.dev')
    res = client.get('/api/v1/issues/CORE-1/suggestions')
    assert res.status_code == 200
    data = res.get_json()['data']
    assert len(data['debugging_steps']) > 0
    assert data['classification']['suggested_category'] == 'database'

    missing = client.get('/api/v1/issues/NOPE-999')
    assert missing.status_code == 404
    assert missing.get_json()['success'] is False


def test_api_analytics_charts_and_csv_export(client, sample_data):
    login(client, 'admin@test.dev')
    for chart in ['status', 'severity', 'category', 'timeline']:
        res = client.get(f'/api/v1/analytics/charts/{chart}')
        assert res.status_code == 200
        j = res.get_json()
        assert j['success'] is True
        assert 'labels' in j['data'] and 'values' in j['data']

    bad = client.get('/api/v1/analytics/charts/unknown')
    assert bad.status_code == 400

    csv_res = client.get('/admin/analytics/export')
    assert csv_res.status_code == 200
    assert 'text/csv' in csv_res.content_type
    assert b'Issue Key,Title' in csv_res.data
    assert b'CORE-1' in csv_res.data


def test_analytics_service_calculations(app, sample_data):
    stats = AnalyticsService.get_overview_stats()
    assert stats['total_issues'] == 3
    assert stats['critical_issues'] == 2
    assert stats['active_projects'] == 2

    health = AnalyticsService.get_backlog_health()
    assert health['total_open'] == 3
    assert health['unassigned'] == 2

    sprint_metrics = AnalyticsService.get_sprint_metrics(sample_data['sprint'].id)
    assert sprint_metrics['total_issues'] == 1
    assert sprint_metrics['completed'] == 0
