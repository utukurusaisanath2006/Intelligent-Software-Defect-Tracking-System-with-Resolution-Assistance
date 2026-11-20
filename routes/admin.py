"""Administration module: users, projects, audit logs, analytics, and system settings."""

import csv
import io
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, Response, current_app
from flask_login import login_required, current_user
from extensions import db
from models.user import User
from models.project import Project, ProjectMembership
from models.issue import Issue
from models.activity import Activity
from services.analytics_service import AnalyticsService

admin_bp = Blueprint('admin', __name__)


@admin_bp.before_request
@login_required
def require_admin():
    """Enforce administrator role across all admin endpoints."""
    if not current_user.is_admin:
        abort(403)


@admin_bp.route('/overview')
def overview():
    """Admin executive dashboard with quality metrics and activity."""
    stats = AnalyticsService.get_overview_stats()
    recent_activities = Activity.query.order_by(Activity.created_at.desc()).limit(15).all()
    recent_issues = Issue.query.order_by(Issue.created_at.desc()).limit(8).all()
    projects = Project.query.filter_by(status=Project.STATUS_ACTIVE).all()

    return render_template(
        'admin/overview.html',
        stats=stats,
        recent_activities=recent_activities,
        recent_issues=recent_issues,
        projects=projects,
    )


# ---------------- User Management ----------------

@admin_bp.route('/users')
def users():
    """List and filter users."""
    role_filter = request.args.get('role')
    active_filter = request.args.get('active')
    search = request.args.get('q', '').strip()

    query = User.query
    if role_filter:
        query = query.filter_by(role=role_filter)
    if active_filter is not None and active_filter != '':
        query = query.filter_by(is_active=(active_filter == '1'))
    if search:
        s = f"%{search}%"
        query = query.filter(
            (User.username.ilike(s)) |
            (User.email.ilike(s)) |
            (User.first_name.ilike(s)) |
            (User.last_name.ilike(s))
        )

    users_list = query.order_by(User.created_at.desc()).all()
    return render_template(
        'admin/users.html',
        users=users_list,
        role_filter=role_filter,
        active_filter=active_filter,
        search=search,
        valid_roles=User.VALID_ROLES,
    )


@admin_bp.route('/users/new', methods=['GET', 'POST'])
def create_user():
    """Create a new user account."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', User.ROLE_REPORTER)

        if not username or not email or not password:
            flash('Username, email, and password are required.', 'error')
            return render_template('admin/user_form.html', is_edit=False, valid_roles=User.VALID_ROLES)

        if User.query.filter_by(email=email).first():
            flash('Email is already registered.', 'error')
            return render_template('admin/user_form.html', is_edit=False, valid_roles=User.VALID_ROLES)

        if User.query.filter_by(username=username).first():
            flash('Username is already taken.', 'error')
            return render_template('admin/user_form.html', is_edit=False, valid_roles=User.VALID_ROLES)

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role if role in User.VALID_ROLES else User.ROLE_REPORTER,
            is_active=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # Audit activity
        act = Activity(
            actor_id=current_user.id,
            event_type=Activity.EVT_USER_CREATED,
            details=f"User {user.username} ({user.email}) created with role {user.role}",
        )
        db.session.add(act)
        db.session.commit()

        flash(f'User {user.full_name} created successfully.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', is_edit=False, valid_roles=User.VALID_ROLES)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    """Edit user details and role."""
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.first_name = request.form.get('first_name', '').strip()
        user.last_name = request.form.get('last_name', '').strip()
        new_role = request.form.get('role')
        password = request.form.get('password')

        # Safety check: Prevent removing admin role from last active admin
        if user.is_admin and new_role != User.ROLE_ADMIN:
            admin_count = User.query.filter_by(role=User.ROLE_ADMIN, is_active=True).count()
            if admin_count <= 1:
                flash('Cannot revoke admin role from the sole active administrator.', 'error')
                return render_template('admin/user_form.html', is_edit=True, user=user, valid_roles=User.VALID_ROLES)

        if new_role in User.VALID_ROLES:
            user.role = new_role

        if password and len(password) >= 6:
            user.set_password(password)

        act = Activity(
            actor_id=current_user.id,
            event_type=Activity.EVT_USER_UPDATED,
            details=f"User {user.username} profile updated",
        )
        db.session.add(act)
        db.session.commit()

        flash(f'User {user.full_name} updated successfully.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', is_edit=True, user=user, valid_roles=User.VALID_ROLES)


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
def toggle_user_active(user_id):
    """Activate or deactivate user account."""
    user = User.query.get_or_404(user_id)

    # Safety: Cannot deactivate self or the last active admin
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('admin.users'))

    if user.is_admin and user.is_active:
        admin_count = User.query.filter_by(role=User.ROLE_ADMIN, is_active=True).count()
        if admin_count <= 1:
            flash('Cannot deactivate the sole remaining active administrator.', 'error')
            return redirect(url_for('admin.users'))

    user.is_active = not user.is_active
    status_str = "activated" if user.is_active else "deactivated"

    act = Activity(
        actor_id=current_user.id,
        event_type=Activity.EVT_USER_UPDATED,
        details=f"User {user.username} was {status_str}",
    )
    db.session.add(act)
    db.session.commit()

    flash(f'User {user.full_name} has been {status_str}.', 'success')
    return redirect(url_for('admin.users'))


# ---------------- Project Management ----------------

@admin_bp.route('/projects')
def projects():
    """List all projects for administration."""
    all_projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template('admin/projects.html', projects=all_projects)


@admin_bp.route('/projects/new', methods=['GET', 'POST'])
def create_project():
    """Create a new project."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        key = request.form.get('key', '').strip().upper()
        description = request.form.get('description', '').strip()

        if not name or not key:
            flash('Project name and key are required.', 'error')
            return render_template('admin/project_form.html', is_edit=False)

        if Project.query.filter_by(key=key).first():
            flash(f'Project key "{key}" is already in use.', 'error')
            return render_template('admin/project_form.html', is_edit=False)

        project = Project(name=name, key=key, description=description, status=Project.STATUS_ACTIVE)
        db.session.add(project)
        db.session.flush()

        # Add creator as manager
        membership = ProjectMembership(user_id=current_user.id, project_id=project.id, role='manager')
        db.session.add(membership)

        act = Activity(
            actor_id=current_user.id,
            project_id=project.id,
            event_type=Activity.EVT_PROJECT_CREATED,
            details=f"Project {project.key} ({project.name}) created",
        )
        db.session.add(act)
        db.session.commit()

        flash(f'Project "{name}" ({key}) created successfully.', 'success')
        return redirect(url_for('admin.projects'))

    return render_template('admin/project_form.html', is_edit=False)


@admin_bp.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
def edit_project(project_id):
    """Edit project properties."""
    project = Project.query.get_or_404(project_id)

    if request.method == 'POST':
        project.name = request.form.get('name', project.name).strip()
        project.description = request.form.get('description', project.description).strip()
        new_status = request.form.get('status', project.status)
        if new_status in [Project.STATUS_ACTIVE, Project.STATUS_ARCHIVED]:
            project.status = new_status

        act = Activity(
            actor_id=current_user.id,
            project_id=project.id,
            event_type=Activity.EVT_PROJECT_UPDATED,
            details=f"Project {project.key} configuration updated",
        )
        db.session.add(act)
        db.session.commit()

        flash(f'Project {project.name} updated successfully.', 'success')
        return redirect(url_for('admin.projects'))

    return render_template('admin/project_form.html', is_edit=True, project=project)


@admin_bp.route('/projects/<int:project_id>/archive', methods=['POST'])
def archive_project(project_id):
    """Archive project while preserving issue and audit history."""
    project = Project.query.get_or_404(project_id)
    project.status = Project.STATUS_ARCHIVED

    act = Activity(
        actor_id=current_user.id,
        project_id=project.id,
        event_type=Activity.EVT_PROJECT_UPDATED,
        details=f"Project {project.key} was archived",
    )
    db.session.add(act)
    db.session.commit()

    flash(f'Project {project.name} has been archived.', 'info')
    return redirect(url_for('admin.projects'))


@admin_bp.route('/projects/<int:project_id>/members', methods=['POST'])
def manage_project_members(project_id):
    """Add or remove members from a project."""
    project = Project.query.get_or_404(project_id)
    action = request.form.get('action')
    user_id = request.form.get('user_id', type=int)

    if action == 'add' and user_id:
        if not ProjectMembership.query.filter_by(project_id=project.id, user_id=user_id).first():
            m = ProjectMembership(project_id=project.id, user_id=user_id, role='member')
            db.session.add(m)
            db.session.commit()
            flash('Member added to project.', 'success')
    elif action == 'remove' and user_id:
        m = ProjectMembership.query.filter_by(project_id=project.id, user_id=user_id).first()
        if m:
            db.session.delete(m)
            db.session.commit()
            flash('Member removed from project.', 'info')

    return redirect(url_for('projects.view_project', project_id=project_id))


# ---------------- Analytics & CSV Export ----------------

@admin_bp.route('/analytics')
def analytics():
    """Quality metrics, defect density, resolution times, and team workload."""
    project_id = request.args.get('project_id', type=int)
    projects = Project.query.filter_by(status=Project.STATUS_ACTIVE).all()

    stats = AnalyticsService.get_overview_stats(project_id=project_id)
    resolution_times = AnalyticsService.get_resolution_times(project_id=project_id)
    backlog_health = AnalyticsService.get_backlog_health(project_id=project_id)
    developer_workload = AnalyticsService.get_developer_workload(project_id=project_id)
    project_comparison = AnalyticsService.get_project_comparison()

    return render_template(
        'admin/analytics.html',
        projects=projects,
        selected_project_id=project_id,
        stats=stats,
        resolution_times=resolution_times,
        backlog_health=backlog_health,
        developer_workload=developer_workload,
        project_comparison=project_comparison,
    )


@admin_bp.route('/analytics/export')
def export_csv():
    """Export filtered issue data as CSV."""
    project_id = request.args.get('project_id', type=int)
    query = Issue.query
    if project_id:
        query = query.filter_by(project_id=project_id)

    issues = query.order_by(Issue.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Issue Key', 'Title', 'Type', 'Category', 'Severity', 'Priority',
        'Status', 'Project', 'Component', 'Reporter', 'Assignee',
        'Created At', 'Resolved At'
    ])

    for issue in issues:
        writer.writerow([
            issue.issue_key,
            issue.title,
            issue.issue_type,
            issue.category,
            issue.severity,
            issue.priority,
            issue.status,
            issue.project.name if issue.project else '',
            issue.component,
            issue.reporter.full_name if issue.reporter else '',
            issue.assignee.full_name if issue.assignee else 'Unassigned',
            issue.created_at.strftime('%Y-%m-%d %H:%M:%S') if issue.created_at else '',
            issue.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if issue.resolved_at else '',
        ])

    output.seek(0)
    filename = f"intellitrack_issues_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ---------------- Audit Log ----------------

@admin_bp.route('/activity')
def activity_log():
    """Audit history of all workflow events, modifications, and administrative operations."""
    page = request.args.get('page', 1, type=int)
    per_page = 30
    event_type = request.args.get('event_type')
    actor_id = request.args.get('actor_id', type=int)

    query = Activity.query
    if event_type:
        query = query.filter_by(event_type=event_type)
    if actor_id:
        query = query.filter_by(actor_id=actor_id)

    pagination = query.order_by(Activity.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    users = User.query.filter_by(is_active=True).all()

    return render_template(
        'admin/activity.html',
        pagination=pagination,
        activities=pagination.items,
        users=users,
        selected_event=event_type,
        selected_actor_id=actor_id,
    )


# ---------------- Settings ----------------

@admin_bp.route('/settings')
def settings():
    """System configuration parameters and workflow rules."""
    return render_template(
        'admin/settings.html',
        app_config=current_app.config,
    )
