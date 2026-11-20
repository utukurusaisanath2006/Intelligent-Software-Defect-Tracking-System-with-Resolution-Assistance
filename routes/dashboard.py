"""Role-specific dashboard routes."""

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from models.issue import Issue
from models.activity import Activity
from models.project import Project, ProjectMembership
from services.analytics_service import AnalyticsService

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def root():
    """Redirect to role-specific dashboard."""
    return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/dashboard')
@login_required
def index():
    """Render role-specific dashboard based on current user role."""
    if current_user.is_admin:
        return redirect(url_for('admin.overview'))
    elif current_user.is_developer:
        return developer_dashboard()
    else:
        return reporter_dashboard()


def developer_dashboard():
    """Developer focused workspace."""
    # Assigned open issues
    assigned_query = Issue.query.filter_by(assignee_id=current_user.id)
    
    assigned_open = assigned_query.filter(Issue.status.in_(Issue.OPEN_STATUSES)).order_by(Issue.priority.asc(), Issue.created_at.desc()).all()
    in_progress = assigned_query.filter(Issue.status == Issue.STATUS_IN_PROGRESS).all()
    critical_assigned = assigned_query.filter(
        Issue.severity == Issue.SEV_CRITICAL,
        Issue.status.in_(Issue.OPEN_STATUSES)
    ).all()
    awaiting_qa = assigned_query.filter(Issue.status == Issue.STATUS_QA_VERIFICATION).all()
    recently_resolved = assigned_query.filter(
        Issue.status.in_([Issue.STATUS_RESOLVED, Issue.STATUS_CLOSED])
    ).order_by(Issue.resolved_at.desc()).limit(5).all()

    # Recent activity for assigned issues
    assigned_issue_ids = [i.id for i in assigned_query.all()]
    recent_activities = Activity.query.filter(
        Activity.issue_id.in_(assigned_issue_ids) if assigned_issue_ids else False
    ).order_by(Activity.created_at.desc()).limit(10).all()

    # Workload summary
    stats = {
        'assigned_open': len(assigned_open),
        'in_progress': len(in_progress),
        'critical': len(critical_assigned),
        'awaiting_qa': len(awaiting_qa),
        'resolved_count': len(recently_resolved),
    }

    return render_template(
        'dashboards/developer.html',
        stats=stats,
        work_queue=assigned_open,
        in_progress_issues=in_progress,
        critical_issues=critical_assigned,
        awaiting_qa_issues=awaiting_qa,
        recent_activities=recent_activities,
    )


def reporter_dashboard():
    """Reporter and QA focused workspace."""
    # Issues reported by current user
    reported_query = Issue.query.filter_by(reporter_id=current_user.id)

    total_reported = reported_query.count()
    open_reported = reported_query.filter(Issue.status.in_(Issue.OPEN_STATUSES)).order_by(Issue.created_at.desc()).all()
    in_progress = reported_query.filter(Issue.status.in_([Issue.STATUS_IN_PROGRESS, Issue.STATUS_CODE_REVIEW])).all()
    awaiting_verification = reported_query.filter(Issue.status == Issue.STATUS_QA_VERIFICATION).all()
    recently_resolved = reported_query.filter(
        Issue.status.in_([Issue.STATUS_RESOLVED, Issue.STATUS_CLOSED])
    ).order_by(Issue.resolved_at.desc()).limit(5).all()

    # Accessible projects
    if current_user.is_admin:
        projects = Project.query.filter_by(status=Project.STATUS_ACTIVE).all()
    else:
        projects = Project.query.join(ProjectMembership).filter(
            ProjectMembership.user_id == current_user.id,
            Project.status == Project.STATUS_ACTIVE
        ).all()

    # Recent activity on user's reported issues
    reported_issue_ids = [i.id for i in reported_query.all()]
    recent_activities = Activity.query.filter(
        Activity.issue_id.in_(reported_issue_ids) if reported_issue_ids else False
    ).order_by(Activity.created_at.desc()).limit(10).all()

    stats = {
        'total_reported': total_reported,
        'open_reported': len(open_reported),
        'in_progress': len(in_progress),
        'awaiting_verification': len(awaiting_verification),
        'recently_resolved': len(recently_resolved),
    }

    return render_template(
        'dashboards/reporter.html',
        stats=stats,
        recent_issues=open_reported[:10],
        awaiting_verification=awaiting_verification,
        projects=projects,
        recent_activities=recent_activities,
    )
