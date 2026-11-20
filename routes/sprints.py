"""Sprint planning and release tracking routes."""

from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from models.sprint import Sprint
from models.project import Project, ProjectMembership
from models.issue import Issue
from services.analytics_service import AnalyticsService

sprints_bp = Blueprint('sprints', __name__)


@sprints_bp.route('/')
@login_required
def list_sprints():
    """List sprints for accessible projects."""
    if current_user.is_admin:
        projects = Project.query.filter_by(status=Project.STATUS_ACTIVE).all()
        sprints = Sprint.query.order_by(Sprint.created_at.desc()).all()
    else:
        projects = Project.query.join(ProjectMembership).filter(
            ProjectMembership.user_id == current_user.id
        ).all()
        project_ids = [p.id for p in projects]
        sprints = Sprint.query.filter(Sprint.project_id.in_(project_ids)).order_by(Sprint.created_at.desc()).all()

    return render_template(
        'sprints/list.html',
        sprints=sprints,
        projects=projects,
    )


@sprints_bp.route('/<int:sprint_id>')
@login_required
def view_sprint(sprint_id):
    """View sprint board, issue backlog, and velocity metrics."""
    sprint = Sprint.query.get_or_404(sprint_id)

    if not current_user.is_admin and not current_user.has_project_access(sprint.project_id):
        abort(403)

    metrics = AnalyticsService.get_sprint_metrics(sprint_id)
    sprint_issues = sprint.issues.order_by(Issue.priority.asc(), Issue.created_at.desc()).all()

    # Backlog issues in same project not yet assigned to any sprint
    backlog_issues = Issue.query.filter_by(
        project_id=sprint.project_id,
        sprint_id=None
    ).filter(Issue.status.in_(Issue.OPEN_STATUSES)).all()

    return render_template(
        'sprints/detail.html',
        sprint=sprint,
        metrics=metrics,
        issues=sprint_issues,
        backlog_issues=backlog_issues,
    )


@sprints_bp.route('/new', methods=['POST'])
@login_required
def create_sprint():
    """Create a new sprint."""
    if not current_user.is_admin and not current_user.is_developer:
        abort(403)

    project_id = request.form.get('project_id', type=int)
    name = request.form.get('name', '').strip()
    goal = request.form.get('goal', '').strip()
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')

    if not name or not project_id:
        flash('Sprint name and project are required.', 'error')
        return redirect(url_for('sprints.list_sprints'))

    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

    sprint = Sprint(
        name=name,
        project_id=project_id,
        goal=goal,
        start_date=start_date,
        end_date=end_date,
        status=Sprint.STATUS_PLANNING,
    )
    db.session.add(sprint)
    db.session.commit()

    flash(f'Sprint "{name}" created.', 'success')
    return redirect(url_for('sprints.view_sprint', sprint_id=sprint.id))


@sprints_bp.route('/<int:sprint_id>/add-issue', methods=['POST'])
@login_required
def add_issue_to_sprint(sprint_id):
    """Add backlog issue to sprint."""
    sprint = Sprint.query.get_or_404(sprint_id)
    if not current_user.is_admin and not current_user.has_project_access(sprint.project_id):
        abort(403)

    issue_id = request.form.get('issue_id', type=int)
    issue = Issue.query.get(issue_id) if issue_id else None

    if issue and issue.project_id == sprint.project_id:
        issue.sprint_id = sprint.id
        db.session.commit()
        flash(f'Issue {issue.issue_key} added to sprint.', 'success')
    else:
        flash('Invalid issue selection.', 'error')

    return redirect(url_for('sprints.view_sprint', sprint_id=sprint_id))


@sprints_bp.route('/<int:sprint_id>/status', methods=['POST'])
@login_required
def update_sprint_status(sprint_id):
    """Change sprint status (planning -> active -> completed)."""
    sprint = Sprint.query.get_or_404(sprint_id)
    if not current_user.is_admin and not current_user.is_developer:
        abort(403)

    new_status = request.form.get('status')
    if new_status in Sprint.VALID_STATUSES:
        sprint.status = new_status
        db.session.commit()
        flash(f'Sprint status updated to {new_status.title()}.', 'success')
    else:
        flash('Invalid sprint status.', 'error')

    return redirect(url_for('sprints.view_sprint', sprint_id=sprint_id))
