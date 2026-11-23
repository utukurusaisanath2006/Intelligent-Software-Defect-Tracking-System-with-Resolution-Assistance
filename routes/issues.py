"""Issue management routes: listing, creation, details, transitions, and collaboration."""

import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from extensions import db
from models.issue import Issue
from models.project import Project, ProjectMembership
from models.user import User
from models.comment import Comment
from models.attachment import Attachment
from models.sprint import Sprint
from models.release import Release
from services.issue_service import IssueService
from services.workflow_service import WorkflowService
from services.classification_service import ClassificationService
from services.resolution_assistant import ResolutionAssistant
from services.notification_service import NotificationService

issues_bp = Blueprint('issues', __name__)


def check_project_access(project_id):
    """Enforce project-level access control."""
    if current_user.is_admin:
        return True
    return ProjectMembership.query.filter_by(
        user_id=current_user.id, project_id=project_id
    ).first() is not None


def validate_magic_bytes(file_path, ext):
    """Inspect file header magic bytes to verify content matches claimed extension and block executables."""
    signatures = {
        'png': [b'\x89PNG\r\n\x1a\n'],
        'jpg': [b'\xff\xd8\xff'],
        'jpeg': [b'\xff\xd8\xff'],
        'gif': [b'GIF87a', b'GIF89a'],
        'pdf': [b'%PDF-'],
        'zip': [b'PK\x03\x04'],
    }
    try:
        with open(file_path, 'rb') as f:
            header = f.read(32)
            # Block executable binaries and dangerous scripts disguised as uploads
            if header.startswith((b'MZ', b'\x7fELF', b'\xca\xfe\xba\xbe', b'#!/bin/', b'<?php')):
                return False
            if ext in signatures:
                return any(header.startswith(sig) for sig in signatures[ext])
            return True
    except Exception:
        return False


@issues_bp.route('/')
@login_required
def list_issues():
    """Browse, filter, and search issues with server-side pagination."""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 20)
    sort_by = request.args.get('sort_by', 'created_at')
    sort_dir = request.args.get('sort_dir', 'desc')

    filters = {
        'project_id': request.args.get('project_id'),
        'status': request.args.get('status'),
        'severity': request.args.get('severity'),
        'priority': request.args.get('priority'),
        'issue_type': request.args.get('issue_type'),
        'assignee_id': request.args.get('assignee_id'),
        'reporter_id': request.args.get('reporter_id'),
        'search': request.args.get('q', '').strip(),
    }

    pagination = IssueService.get_issues(
        filters=filters,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        user=current_user
    )

    # Get dropdown options
    if current_user.is_admin:
        projects = Project.query.filter_by(status=Project.STATUS_ACTIVE).all()
        users = User.query.filter_by(is_active=True).all()
    else:
        projects = Project.query.join(ProjectMembership).filter(
            ProjectMembership.user_id == current_user.id,
            Project.status == Project.STATUS_ACTIVE
        ).all()
        project_ids = [p.id for p in projects]
        users = User.query.join(ProjectMembership).filter(
            ProjectMembership.project_id.in_(project_ids),
            User.is_active == True
        ).distinct().all()

    return render_template(
        'issues/list.html',
        pagination=pagination,
        issues=pagination.items,
        projects=projects,
        users=users,
        filters=filters,
        sort_by=sort_by,
        sort_dir=sort_dir,
        valid_statuses=Issue.VALID_STATUSES,
        valid_severities=Issue.VALID_SEVERITIES,
        valid_priorities=Issue.VALID_PRIORITIES,
        valid_types=Issue.VALID_TYPES,
    )


@issues_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create_issue():
    """Report a new defect or request."""
    # Accessible projects
    if current_user.is_admin:
        projects = Project.query.filter_by(status=Project.STATUS_ACTIVE).all()
    else:
        projects = Project.query.join(ProjectMembership).filter(
            ProjectMembership.user_id == current_user.id,
            Project.status == Project.STATUS_ACTIVE
        ).all()

    if not projects:
        flash('You do not belong to any active project to report issues in.', 'error')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        project_id = request.form.get('project_id', type=int)
        if not project_id or not check_project_access(project_id):
            flash('Invalid project selection.', 'error')
            return redirect(url_for('issues.create_issue'))

        project = Project.query.get_or_404(project_id)
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        issue_type = request.form.get('issue_type', Issue.TYPE_BUG)

        if not title:
            flash('Issue title is required.', 'error')
            return redirect(url_for('issues.create_issue'))

        # Run classification recommendation if fields are omitted
        classification = ClassificationService.classify_issue(
            title=title,
            description=description,
            component=request.form.get('component', ''),
            issue_type=issue_type
        )

        category = request.form.get('category') or classification['suggested_category']
        severity = request.form.get('severity') or classification['suggested_severity']
        priority = request.form.get('priority') or classification['suggested_priority']

        data = {
            'title': title,
            'description': description,
            'issue_type': issue_type,
            'category': category,
            'severity': severity,
            'priority': priority,
            'component': request.form.get('component', '').strip(),
            'environment': request.form.get('environment', '').strip(),
            'steps_to_reproduce': request.form.get('steps_to_reproduce', '').strip(),
            'expected_result': request.form.get('expected_result', '').strip(),
            'actual_result': request.form.get('actual_result', '').strip(),
        }

        issue = IssueService.create_issue(data, reporter=current_user, project=project)

        # Handle file attachment if provided
        file = request.files.get('attachment')
        if file and file.filename:
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            if ext in current_app.config['ALLOWED_EXTENSIONS']:
                unique_name = f"{issue.issue_key}_{int(issue.created_at.timestamp())}_{filename}"
                dest = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name)
                file.save(dest)
                file_size = os.path.getsize(dest)

                attachment = Attachment(
                    issue_id=issue.id,
                    uploader_id=current_user.id,
                    stored_filename=unique_name,
                    original_filename=filename,
                    content_type=file.content_type or 'application/octet-stream',
                    file_size=file_size,
                )
                db.session.add(attachment)
                db.session.commit()

        flash(f'Issue {issue.issue_key} was created successfully.', 'success')
        return redirect(url_for('issues.view_issue', key=issue.issue_key))

    return render_template(
        'issues/create.html',
        projects=projects,
        valid_types=Issue.VALID_TYPES,
        valid_severities=Issue.VALID_SEVERITIES,
        valid_priorities=Issue.VALID_PRIORITIES,
        valid_categories=Issue.VALID_CATEGORIES,
    )


@issues_bp.route('/<key>')
@login_required
def view_issue(key):
    """View issue details, reproduction steps, activity, comments, and suggestions."""
    issue = IssueService.get_issue_by_key(key)
    if not issue:
        abort(404)

    if not check_project_access(issue.project_id):
        abort(403)

    # Available workflow transitions for current user
    available_transitions = WorkflowService.get_available_transitions(issue, current_user)

    # Resolution assistance
    suggestions = ResolutionAssistant.get_suggestions(issue)

    # Assignable users (developers & admins in project)
    assignable_users = User.query.join(ProjectMembership).filter(
        ProjectMembership.project_id == issue.project_id,
        User.role.in_(['developer', 'admin']),
        User.is_active == True
    ).all()

    # Active sprints for assignment if applicable
    sprints = Sprint.query.filter_by(
        project_id=issue.project_id,
        status=Sprint.STATUS_ACTIVE
    ).all()

    # Releases for this project
    releases = Release.query.filter_by(
        project_id=issue.project_id
    ).order_by(Release.created_at.desc()).all()

    return render_template(
        'issues/detail.html',
        issue=issue,
        available_transitions=available_transitions,
        suggestions=suggestions,
        assignable_users=assignable_users,
        sprints=sprints,
        releases=releases,
        valid_statuses=Issue.VALID_STATUSES,
        valid_severities=Issue.VALID_SEVERITIES,
        valid_priorities=Issue.VALID_PRIORITIES,
        valid_categories=Issue.VALID_CATEGORIES,
    )


@issues_bp.route('/<key>/transition', methods=['POST'])
@login_required
def transition_issue(key):
    """Execute a workflow status transition."""
    issue = IssueService.get_issue_by_key(key)
    if not issue:
        abort(404)

    if not check_project_access(issue.project_id):
        abort(403)

    target_status = request.form.get('target_status')
    notes = request.form.get('notes', '').strip()

    success, message = WorkflowService.transition_issue(
        issue=issue,
        new_status=target_status,
        user=current_user,
        notes=notes
    )

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')

    return redirect(url_for('issues.view_issue', key=key))


@issues_bp.route('/<key>/comment', methods=['POST'])
@login_required
def add_comment(key):
    """Add a collaborative discussion comment."""
    issue = IssueService.get_issue_by_key(key)
    if not issue:
        abort(404)

    if not check_project_access(issue.project_id):
        abort(403)

    body = request.form.get('body', '').strip()
    if not body:
        flash('Comment cannot be empty.', 'error')
        return redirect(url_for('issues.view_issue', key=key))

    comment = Comment(
        issue_id=issue.id,
        author_id=current_user.id,
        body=body
    )
    db.session.add(comment)
    db.session.commit()

    NotificationService.notify_comment_added(issue, comment, current_user)
    flash('Comment added.', 'success')
    return redirect(url_for('issues.view_issue', key=key))


@issues_bp.route('/<key>/assign', methods=['POST'])
@login_required
def assign_issue(key):
    """Assign or reassign an issue."""
    issue = IssueService.get_issue_by_key(key)
    if not issue:
        abort(404)

    if not check_project_access(issue.project_id):
        abort(403)

    # Permission check: admin or developer in project
    if not current_user.is_admin and not current_user.is_developer:
        abort(403)

    assignee_id = request.form.get('assignee_id', type=int)
    assignee = User.query.get(assignee_id) if assignee_id else None

    IssueService.assign_issue(issue, assignee, actor=current_user)
    flash(f'Issue assigned to {assignee.full_name if assignee else "Unassigned"}.', 'success')
    return redirect(url_for('issues.view_issue', key=key))


@issues_bp.route('/<key>/assign-release', methods=['POST'])
@login_required
def assign_release(key):
    """Assign or unassign an issue to/from a release."""
    issue = IssueService.get_issue_by_key(key)
    if not issue:
        abort(404)

    if not check_project_access(issue.project_id):
        abort(403)

    if not current_user.is_admin and not current_user.is_developer:
        abort(403)

    release_id = request.form.get('release_id', type=int)
    if release_id:
        release = Release.query.get(release_id)
        if release and release.project_id == issue.project_id:
            issue.release_id = release.id
            db.session.commit()
            flash(f'Issue assigned to release {release.name}.', 'success')
        else:
            flash('Invalid release selected.', 'error')
    else:
        issue.release_id = None
        db.session.commit()
        flash('Issue removed from release.', 'success')

    return redirect(url_for('issues.view_issue', key=key))


@issues_bp.route('/<key>/update', methods=['POST'])
@login_required
def update_issue(key):
    """Update issue metadata, root cause, and resolution details."""
    issue = IssueService.get_issue_by_key(key)
    if not issue:
        abort(404)

    if not check_project_access(issue.project_id):
        abort(403)

    # Permission check
    can_edit = (
        current_user.is_admin or
        current_user.id == issue.assignee_id or
        current_user.id == issue.reporter_id
    )
    if not can_edit:
        abort(403)

    data = {
        'title': request.form.get('title', issue.title),
        'description': request.form.get('description', issue.description),
        'severity': request.form.get('severity', issue.severity),
        'priority': request.form.get('priority', issue.priority),
        'category': request.form.get('category', issue.category),
        'component': request.form.get('component', issue.component),
        'environment': request.form.get('environment', issue.environment),
        'steps_to_reproduce': request.form.get('steps_to_reproduce', issue.steps_to_reproduce),
        'expected_result': request.form.get('expected_result', issue.expected_result),
        'actual_result': request.form.get('actual_result', issue.actual_result),
        'root_cause': request.form.get('root_cause', issue.root_cause),
        'resolution_notes': request.form.get('resolution_notes', issue.resolution_notes),
    }

    sprint_id = request.form.get('sprint_id', type=int)
    if sprint_id != issue.sprint_id:
        issue.sprint_id = sprint_id if sprint_id else None

    issue, changes = IssueService.update_issue(issue, data, user=current_user)
    flash('Issue details updated successfully.', 'success')
    return redirect(url_for('issues.view_issue', key=key))


@issues_bp.route('/<key>/attachment', methods=['POST'])
@login_required
def upload_attachment(key):
    """Upload screenshot or error log attachment."""
    issue = IssueService.get_issue_by_key(key)
    if not issue:
        abort(404)

    if not check_project_access(issue.project_id):
        abort(403)

    file = request.files.get('file')
    if not file or not file.filename:
        flash('No file was selected for upload.', 'error')
        return redirect(url_for('issues.view_issue', key=key))

    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext not in current_app.config['ALLOWED_EXTENSIONS']:
        flash(f'File type .{ext} is not allowed. Supported: {", ".join(current_app.config["ALLOWED_EXTENSIONS"])}', 'error')
        return redirect(url_for('issues.view_issue', key=key))

    unique_name = f"{issue.issue_key}_{int(issue.created_at.timestamp())}_{filename}"
    dest = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_name)
    file.save(dest)

    if not validate_magic_bytes(dest, ext):
        try:
            os.remove(dest)
        except OSError:
            pass
        current_app.logger.warning(f"Security Alert: Disguised or executable file upload rejected: {filename} from ip={request.remote_addr}")
        flash('Upload rejected: File content does not match its declared format or contains disallowed binary content.', 'error')
        return redirect(url_for('issues.view_issue', key=key))

    file_size = os.path.getsize(dest)

    attachment = Attachment(
        issue_id=issue.id,
        uploader_id=current_user.id,
        stored_filename=unique_name,
        original_filename=filename,
        content_type=file.content_type or 'application/octet-stream',
        file_size=file_size,
    )
    db.session.add(attachment)
    db.session.commit()

    flash(f'Attachment {filename} uploaded successfully.', 'success')
    return redirect(url_for('issues.view_issue', key=key))


@issues_bp.route('/<key>/attachments/<int:attachment_id>/download', methods=['GET'])
@login_required
def download_attachment(key, attachment_id):
    """Securely download an attachment after verifying project and issue access."""
    issue = IssueService.get_issue_by_key(key)
    if not issue:
        abort(404)

    if not check_project_access(issue.project_id):
        abort(403)

    # Validate file access strictly using database records
    attachment = Attachment.query.filter_by(id=attachment_id, issue_id=issue.id).first()
    if not attachment:
        abort(404)

    # Prevent path traversal and filename manipulation
    stored_name = attachment.stored_filename
    if not stored_name or '..' in stored_name or '/' in stored_name or '\\' in stored_name:
        abort(400)

    safe_stored_name = os.path.basename(stored_name)
    if safe_stored_name != stored_name:
        abort(400)

    # Primary upload directory
    upload_folder = os.path.abspath(current_app.config['UPLOAD_FOLDER'])
    file_path = os.path.join(upload_folder, safe_stored_name)
    target_abs = os.path.abspath(file_path)

    # Verify target stays inside upload directory boundary
    if not target_abs.startswith(upload_folder + os.sep) and target_abs != upload_folder:
        abort(403)

    # Check if file exists in primary upload directory; fallback to legacy static/uploads if needed
    if not os.path.isfile(target_abs):
        legacy_folder = os.path.abspath(os.path.join(current_app.root_path, 'static', 'uploads'))
        legacy_file = os.path.join(legacy_folder, safe_stored_name)
        legacy_abs = os.path.abspath(legacy_file)
        if legacy_abs.startswith(legacy_folder + os.sep) and os.path.isfile(legacy_abs):
            upload_folder = legacy_folder
            safe_stored_name = os.path.basename(legacy_file)
        else:
            abort(404)

    response = send_from_directory(
        directory=upload_folder,
        path=safe_stored_name,
        as_attachment=True,
        download_name=attachment.original_filename,
        mimetype=attachment.content_type
    )
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Download-Options'] = 'noopen'
    return response
