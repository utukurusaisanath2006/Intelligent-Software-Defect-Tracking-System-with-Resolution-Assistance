"""Project routes for listing and project detail."""

from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from models.project import Project, ProjectMembership
from models.issue import Issue
from services.analytics_service import AnalyticsService

projects_bp = Blueprint('projects', __name__)


@projects_bp.route('/')
@login_required
def list_projects():
    """List accessible projects."""
    if current_user.is_admin:
        projects = Project.query.all()
    else:
        projects = Project.query.join(ProjectMembership).filter(
            ProjectMembership.user_id == current_user.id
        ).all()

    return render_template('projects/list.html', projects=projects)


@projects_bp.route('/<int:project_id>')
@login_required
def view_project(project_id):
    """View project overview, members, sprints, and recent issues."""
    project = Project.query.get_or_404(project_id)

    if not current_user.is_admin and not current_user.has_project_access(project_id):
        abort(403)

    stats = AnalyticsService.get_overview_stats(project_id=project_id)
    recent_issues = project.issues.order_by(Issue.created_at.desc()).limit(15).all()
    sprints = project.sprints.all()

    return render_template(
        'projects/detail.html',
        project=project,
        stats=stats,
        issues=recent_issues,
        sprints=sprints,
    )
