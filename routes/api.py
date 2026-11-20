"""REST API v1 endpoints for asynchronous interactions, search, and analytics."""

from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from extensions import db
from models.issue import Issue
from models.project import Project
from models.notification import Notification
from services.issue_service import IssueService
from services.workflow_service import WorkflowService
from services.classification_service import ClassificationService
from services.resolution_assistant import ResolutionAssistant
from services.analytics_service import AnalyticsService
from services.notification_service import NotificationService

api_bp = Blueprint('api', __name__)


@api_bp.route('/issues', methods=['GET'])
@login_required
def get_issues():
    """Retrieve paginated issue list in JSON format."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    filters = {
        'project_id': request.args.get('project_id'),
        'status': request.args.get('status'),
        'severity': request.args.get('severity'),
        'priority': request.args.get('priority'),
        'search': request.args.get('q'),
    }

    pagination = IssueService.get_issues(
        filters=filters,
        page=page,
        per_page=per_page,
        user=current_user
    )

    return jsonify({
        'success': True,
        'page': pagination.page,
        'total_pages': pagination.pages,
        'total_items': pagination.total,
        'data': [issue.to_dict() for issue in pagination.items],
    })


@api_bp.route('/issues/<key>', methods=['GET'])
@login_required
def get_issue(key):
    """Retrieve full issue details by key."""
    issue = IssueService.get_issue_by_key(key)
    if not issue:
        return jsonify({'success': False, 'error': f'Issue {key} not found'}), 404

    if not current_user.has_project_access(issue.project_id):
        return jsonify({'success': False, 'error': 'Forbidden'}), 403

    return jsonify({
        'success': True,
        'data': issue.to_dict(),
        'available_transitions': WorkflowService.get_available_transitions(issue, current_user),
    })


@api_bp.route('/issues/<key>/transition', methods=['POST'])
@login_required
def transition_issue(key):
    """Execute workflow transition via JSON API."""
    issue = IssueService.get_issue_by_key(key)
    if not issue:
        return jsonify({'success': False, 'error': f'Issue {key} not found'}), 404

    if not current_user.has_project_access(issue.project_id):
        return jsonify({'success': False, 'error': 'Forbidden'}), 403

    payload = request.get_json(silent=True) or request.form
    target_status = payload.get('target_status')
    notes = payload.get('notes', '')

    success, message = WorkflowService.transition_issue(
        issue=issue,
        new_status=target_status,
        user=current_user,
        notes=notes
    )

    if success:
        return jsonify({
            'success': True,
            'message': message,
            'new_status': issue.status,
            'status_display': issue.status_display,
        })
    else:
        return jsonify({'success': False, 'error': message}), 400


@api_bp.route('/issues/<key>/suggestions', methods=['GET'])
@login_required
def get_suggestions(key):
    """Get deterministic classification, debugging steps, and duplicate matches."""
    issue = IssueService.get_issue_by_key(key)
    if not issue:
        return jsonify({'success': False, 'error': f'Issue {key} not found'}), 404

    if not current_user.has_project_access(issue.project_id):
        return jsonify({'success': False, 'error': 'Forbidden'}), 403

    suggestions = ResolutionAssistant.get_suggestions(issue)
    return jsonify({
        'success': True,
        'data': suggestions,
    })


@api_bp.route('/classify', methods=['POST'])
@login_required
def classify_text():
    """Real-time recommendation of category, severity, and priority for issue drafts."""
    payload = request.get_json(silent=True) or request.form
    title = payload.get('title', '')
    description = payload.get('description', '')
    component = payload.get('component', '')
    issue_type = payload.get('issue_type', 'bug')

    result = ClassificationService.classify_issue(
        title=title,
        description=description,
        component=component,
        issue_type=issue_type
    )

    return jsonify({
        'success': True,
        'data': result,
    })


@api_bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    """Fetch unread notifications for current user."""
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    notifications = NotificationService.get_user_notifications(
        user_id=current_user.id,
        unread_only=unread_only,
        limit=20
    )
    unread_count = NotificationService.get_unread_count(current_user.id)

    return jsonify({
        'success': True,
        'unread_count': unread_count,
        'data': [n.to_dict() for n in notifications],
    })


@api_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a notification as read."""
    success = NotificationService.mark_as_read(notification_id, current_user.id)
    return jsonify({'success': success})


@api_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all user notifications as read."""
    count = NotificationService.mark_all_read(current_user.id)
    return jsonify({'success': True, 'marked_count': count})


@api_bp.route('/search', methods=['GET'])
@login_required
def search():
    """Instant search across issues by key or title."""
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'success': True, 'data': []})

    results = IssueService.search_issues(query_string=query, limit=10)
    # Filter project access
    accessible = [
        issue.to_dict() for issue in results
        if current_user.has_project_access(issue.project_id)
    ]

    return jsonify({
        'success': True,
        'data': accessible,
    })


@api_bp.route('/analytics/overview', methods=['GET'])
@login_required
def analytics_overview():
    """Get high-level summary KPIs."""
    project_id = request.args.get('project_id', type=int)
    stats = AnalyticsService.get_overview_stats(project_id=project_id)
    return jsonify({'success': True, 'data': stats})


@api_bp.route('/analytics/charts/<chart_type>', methods=['GET'])
@login_required
def get_chart_data(chart_type):
    """Fetch structured dataset for Chart.js graphs."""
    project_id = request.args.get('project_id', type=int)

    if chart_type == 'status':
        data = AnalyticsService.get_status_distribution(project_id=project_id)
    elif chart_type == 'severity':
        data = AnalyticsService.get_severity_distribution(project_id=project_id)
    elif chart_type == 'category':
        data = AnalyticsService.get_category_distribution(project_id=project_id)
    elif chart_type == 'timeline':
        days = request.args.get('days', 30, type=int)
        data = AnalyticsService.get_issues_over_time(project_id=project_id, days=days)
    else:
        return jsonify({'success': False, 'error': f'Unknown chart type {chart_type}'}), 400

    return jsonify({'success': True, 'data': data})
