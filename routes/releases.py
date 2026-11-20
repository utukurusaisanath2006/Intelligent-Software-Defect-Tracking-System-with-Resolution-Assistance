"""Release planning and version tracking routes."""

from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from models.release import Release
from models.project import Project, ProjectMembership
from models.issue import Issue

releases_bp = Blueprint('releases', __name__)


@releases_bp.route('/')
@login_required
def list_releases():
    """List releases for accessible projects."""
    project_filter = request.args.get('project_id', type=int)
    status_filter = request.args.get('status', '').strip()

    if current_user.is_admin:
        projects = Project.query.filter_by(status=Project.STATUS_ACTIVE).all()
        query = Release.query
    else:
        projects = Project.query.join(ProjectMembership).filter(
            ProjectMembership.user_id == current_user.id
        ).all()
        project_ids = [p.id for p in projects]
        query = Release.query.filter(Release.project_id.in_(project_ids))

    if project_filter:
        query = query.filter_by(project_id=project_filter)
    if status_filter and status_filter in Release.VALID_STATUSES:
        query = query.filter_by(status=status_filter)

    releases = query.order_by(Release.release_date.desc().nullslast(), Release.created_at.desc()).all()

    return render_template(
        'releases/list.html',
        releases=releases,
        projects=projects,
        selected_project=project_filter,
        selected_status=status_filter,
        valid_statuses=Release.VALID_STATUSES,
    )


@releases_bp.route('/<int:release_id>')
@login_required
def view_release(release_id):
    """View release details, milestones, and associated issues."""
    release = Release.query.get_or_404(release_id)

    if not current_user.is_admin and not current_user.has_project_access(release.project_id):
        abort(403)

    release_issues = release.issues.order_by(Issue.priority.asc(), Issue.created_at.desc()).all()

    # Backlog issues in same project not yet assigned to any release
    backlog_issues = Issue.query.filter_by(
        project_id=release.project_id,
        release_id=None
    ).filter(Issue.status.in_(Issue.OPEN_STATUSES)).all()

    can_manage = current_user.is_admin or (current_user.is_developer and current_user.has_project_access(release.project_id))

    return render_template(
        'releases/detail.html',
        release=release,
        issues=release_issues,
        backlog_issues=backlog_issues,
        can_manage=can_manage,
        valid_statuses=Release.VALID_STATUSES,
    )


@releases_bp.route('/new', methods=['POST'])
@login_required
def create_release():
    """Create a new release."""
    if not current_user.is_admin and not current_user.is_developer:
        abort(403)

    project_id = request.form.get('project_id', type=int)
    name = request.form.get('name', '').strip()
    version = request.form.get('version', '').strip()
    description = request.form.get('description', '').strip()
    status = request.form.get('status', Release.STATUS_PLANNING).strip()
    release_date_str = request.form.get('release_date')

    if not name or not project_id:
        flash('Release name and project are required.', 'error')
        return redirect(url_for('releases.list_releases'))

    # Verify project exists and user has access
    project = Project.query.get_or_404(project_id)
    if not current_user.is_admin and not current_user.has_project_access(project.id):
        abort(403)

    if status not in Release.VALID_STATUSES:
        status = Release.STATUS_PLANNING

    release_date = None
    if release_date_str:
        try:
            release_date = datetime.strptime(release_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format. Expected YYYY-MM-DD.', 'error')
            return redirect(url_for('releases.list_releases'))

    release = Release(
        name=name,
        version=version,
        project_id=project.id,
        description=description,
        status=status,
        release_date=release_date,
    )
    db.session.add(release)
    db.session.commit()

    # Trigger notification
    from services.notification_service import NotificationService
    NotificationService.notify_release_created(release, current_user)

    flash(f'Release "{name}" created successfully.', 'success')
    return redirect(url_for('releases.view_release', release_id=release.id))


@releases_bp.route('/<int:release_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_release(release_id):
    """Edit release information."""
    release = Release.query.get_or_404(release_id)

    if not current_user.is_admin and not (current_user.is_developer and current_user.has_project_access(release.project_id)):
        abort(403)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        version = request.form.get('version', '').strip()
        description = request.form.get('description', '').strip()
        status = request.form.get('status', '').strip()
        release_date_str = request.form.get('release_date')

        if not name:
            flash('Release name is required.', 'error')
            return render_template('releases/edit.html', release=release, valid_statuses=Release.VALID_STATUSES)

        if status in Release.VALID_STATUSES:
            old_status = release.status
            release.status = status
            if old_status != status:
                from services.notification_service import NotificationService
                NotificationService.notify_release_status_changed(release, old_status, status, current_user)

        release.name = name
        release.version = version
        release.description = description

        if release_date_str:
            try:
                release.release_date = datetime.strptime(release_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Invalid date format. Expected YYYY-MM-DD.', 'error')
                return render_template('releases/edit.html', release=release, valid_statuses=Release.VALID_STATUSES)
        else:
            release.release_date = None

        db.session.commit()
        flash(f'Release "{release.name}" updated successfully.', 'success')
        return redirect(url_for('releases.view_release', release_id=release.id))

    return render_template('releases/edit.html', release=release, valid_statuses=Release.VALID_STATUSES)


@releases_bp.route('/<int:release_id>/delete', methods=['POST'])
@login_required
def delete_release(release_id):
    """Safely delete release with safe relationship handling (issues preserved)."""
    release = Release.query.get_or_404(release_id)

    if not current_user.is_admin and not (current_user.is_developer and current_user.has_project_access(release.project_id)):
        abort(403)

    release_name = release.name

    # Safe relationship handling: disassociate all issues from this release so no issues are deleted
    for issue in release.issues:
        issue.release_id = None

    db.session.delete(release)
    db.session.commit()

    flash(f'Release "{release_name}" deleted safely. Associated issues have been retained.', 'success')
    return redirect(url_for('releases.list_releases'))


@releases_bp.route('/<int:release_id>/status', methods=['POST'])
@login_required
def update_release_status(release_id):
    """Quick update of release status."""
    release = Release.query.get_or_404(release_id)

    if not current_user.is_admin and not (current_user.is_developer and current_user.has_project_access(release.project_id)):
        abort(403)

    new_status = request.form.get('status')
    if new_status in Release.VALID_STATUSES:
        old_status = release.status
        release.status = new_status
        db.session.commit()

        if old_status != new_status:
            from services.notification_service import NotificationService
            NotificationService.notify_release_status_changed(release, old_status, new_status, current_user)

        flash(f'Release status updated to {new_status.replace("_", " ").title()}.', 'success')
    else:
        flash('Invalid release status.', 'error')

    return redirect(url_for('releases.view_release', release_id=release.id))


@releases_bp.route('/<int:release_id>/add-issue', methods=['POST'])
@login_required
def add_issue_to_release(release_id):
    """Add project issue to release."""
    release = Release.query.get_or_404(release_id)

    if not current_user.is_admin and not (current_user.is_developer and current_user.has_project_access(release.project_id)):
        abort(403)

    issue_id = request.form.get('issue_id', type=int)
    issue = Issue.query.get(issue_id) if issue_id else None

    if issue and issue.project_id == release.project_id:
        issue.release_id = release.id
        db.session.commit()
        flash(f'Issue {issue.issue_key} added to release {release.name}.', 'success')
    else:
        flash('Invalid issue selection or issue belongs to a different project.', 'error')

    return redirect(url_for('releases.view_release', release_id=release.id))


@releases_bp.route('/<int:release_id>/remove-issue', methods=['POST'])
@login_required
def remove_issue_from_release(release_id):
    """Remove issue from release."""
    release = Release.query.get_or_404(release_id)

    if not current_user.is_admin and not (current_user.is_developer and current_user.has_project_access(release.project_id)):
        abort(403)

    issue_id = request.form.get('issue_id', type=int)
    issue = Issue.query.get(issue_id) if issue_id else None

    if issue and issue.release_id == release.id:
        issue.release_id = None
        db.session.commit()
        flash(f'Issue {issue.issue_key} removed from release.', 'success')
    else:
        flash('Issue is not part of this release.', 'error')

    return redirect(url_for('releases.view_release', release_id=release.id))
