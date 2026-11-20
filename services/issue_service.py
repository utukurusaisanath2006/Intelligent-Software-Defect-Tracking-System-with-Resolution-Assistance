"""Issue service — business logic for issue CRUD and queries."""

from datetime import datetime
from sqlalchemy import or_, func
from extensions import db
from models.issue import Issue
from models.activity import Activity
from models.project import Project, ProjectMembership
from models.user import User


class IssueService:
    """Issue management business logic."""

    @staticmethod
    def create_issue(data, reporter, project):
        """
        Create a new issue.

        Args:
            data: dict with issue fields
            reporter: User who is reporting
            project: Project the issue belongs to

        Returns:
            Issue instance
        """
        issue_key = project.generate_issue_key()

        issue = Issue(
            issue_key=issue_key,
            title=data.get('title', '').strip(),
            description=data.get('description', '').strip(),
            issue_type=data.get('issue_type', Issue.TYPE_BUG),
            category=data.get('category', 'other'),
            severity=data.get('severity', Issue.SEV_MINOR),
            priority=data.get('priority', Issue.PRI_MEDIUM),
            status=Issue.STATUS_REPORTED,
            component=data.get('component', '').strip(),
            environment=data.get('environment', '').strip(),
            steps_to_reproduce=data.get('steps_to_reproduce', '').strip(),
            expected_result=data.get('expected_result', '').strip(),
            actual_result=data.get('actual_result', '').strip(),
            project_id=project.id,
            reporter_id=reporter.id,
        )

        db.session.add(issue)
        db.session.flush()  # Get the ID

        # Record activity
        activity = Activity(
            issue_id=issue.id,
            project_id=project.id,
            actor_id=reporter.id,
            event_type=Activity.EVT_CREATED,
            details=f"Issue {issue_key} created: {issue.title}",
        )
        db.session.add(activity)

        # Notify project members
        from services.notification_service import NotificationService
        NotificationService.notify_issue_created(issue, reporter)

        db.session.commit()
        return issue

    @staticmethod
    def update_issue(issue, data, user):
        """
        Update issue fields. Tracks changes in activity log.

        Returns:
            (Issue, list_of_changes)
        """
        changes = []
        tracked_fields = [
            'title', 'description', 'issue_type', 'category', 'severity',
            'priority', 'component', 'environment', 'steps_to_reproduce',
            'expected_result', 'actual_result', 'root_cause', 'resolution_notes',
        ]

        for field in tracked_fields:
            if field in data:
                old_val = getattr(issue, field, '')
                new_val = data[field].strip() if isinstance(data[field], str) else data[field]
                if old_val != new_val:
                    setattr(issue, field, new_val)
                    changes.append((field, str(old_val)[:200], str(new_val)[:200]))
                    activity = Activity(
                        issue_id=issue.id,
                        project_id=issue.project_id,
                        actor_id=user.id,
                        event_type=Activity.EVT_UPDATED,
                        field_name=field,
                        old_value=str(old_val)[:200],
                        new_value=str(new_val)[:200],
                    )
                    db.session.add(activity)

        issue.updated_at = datetime.utcnow()
        db.session.commit()
        return issue, changes

    @staticmethod
    def get_issues(filters=None, page=1, per_page=20, sort_by='created_at', sort_dir='desc', user=None):
        """
        Query issues with filtering, sorting, and pagination.

        Returns:
            SQLAlchemy pagination object
        """
        query = Issue.query

        # Project access filter
        if user and not user.is_admin:
            accessible_projects = db.session.query(ProjectMembership.project_id).filter_by(
                user_id=user.id
            ).subquery()
            query = query.filter(Issue.project_id.in_(accessible_projects))

        if filters:
            if filters.get('project_id'):
                query = query.filter(Issue.project_id == int(filters['project_id']))
            if filters.get('status'):
                query = query.filter(Issue.status == filters['status'])
            if filters.get('severity'):
                query = query.filter(Issue.severity == filters['severity'])
            if filters.get('priority'):
                query = query.filter(Issue.priority == filters['priority'])
            if filters.get('issue_type'):
                query = query.filter(Issue.issue_type == filters['issue_type'])
            if filters.get('assignee_id'):
                query = query.filter(Issue.assignee_id == int(filters['assignee_id']))
            if filters.get('reporter_id'):
                query = query.filter(Issue.reporter_id == int(filters['reporter_id']))
            if filters.get('search'):
                search = f"%{filters['search']}%"
                query = query.filter(
                    or_(
                        Issue.title.ilike(search),
                        Issue.issue_key.ilike(search),
                        Issue.description.ilike(search),
                    )
                )

        # Sorting
        sort_column = getattr(Issue, sort_by, Issue.created_at)
        if sort_dir == 'asc':
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        return query.paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def get_issue_by_key(key):
        """Find issue by its human-readable key."""
        return Issue.query.filter_by(issue_key=key).first()

    @staticmethod
    def assign_issue(issue, assignee, actor):
        """Assign or reassign an issue."""
        old_assignee_name = issue.assignee.full_name if issue.assignee else 'Unassigned'
        new_assignee_name = assignee.full_name if assignee else 'Unassigned'

        old_assignee_id = issue.assignee_id
        issue.assignee_id = assignee.id if assignee else None
        issue.updated_at = datetime.utcnow()

        # If newly assigned and still in reported/triaging, move to assigned
        if assignee and issue.status in ['reported', 'triaging']:
            issue.status = 'assigned'

        activity = Activity(
            issue_id=issue.id,
            project_id=issue.project_id,
            actor_id=actor.id,
            event_type=Activity.EVT_ASSIGNED,
            field_name='assignee',
            old_value=old_assignee_name,
            new_value=new_assignee_name,
            details=f"Issue assigned to {new_assignee_name}",
        )
        db.session.add(activity)

        # Notify assignee
        if assignee and assignee.id != actor.id:
            from services.notification_service import NotificationService
            NotificationService.notify_issue_assigned(issue, assignee, actor)

        db.session.commit()
        return issue

    @staticmethod
    def get_user_issues(user, role_filter=None):
        """Get issues relevant to a user based on role."""
        if role_filter == 'reported':
            return Issue.query.filter_by(reporter_id=user.id).order_by(Issue.updated_at.desc())
        elif role_filter == 'assigned':
            return Issue.query.filter_by(assignee_id=user.id).order_by(Issue.updated_at.desc())
        elif role_filter == 'verification':
            return Issue.query.filter_by(
                reporter_id=user.id, status='qa_verification'
            ).order_by(Issue.updated_at.desc())
        else:
            return Issue.query.filter(
                or_(Issue.reporter_id == user.id, Issue.assignee_id == user.id)
            ).order_by(Issue.updated_at.desc())

    @staticmethod
    def search_issues(query_string, project_id=None, limit=20):
        """Search issues by title or key."""
        search = f"%{query_string}%"
        query = Issue.query.filter(
            or_(
                Issue.title.ilike(search),
                Issue.issue_key.ilike(search),
            )
        )
        if project_id:
            query = query.filter(Issue.project_id == project_id)
        return query.order_by(Issue.updated_at.desc()).limit(limit).all()

    @staticmethod
    def get_similar_issues(issue, limit=5):
        """Find similar issues using text matching on title and description."""
        if not issue.title:
            return []

        words = issue.title.lower().split()
        # Use significant words (>3 chars)
        keywords = [w for w in words if len(w) > 3][:5]

        if not keywords:
            return []

        conditions = []
        for kw in keywords:
            conditions.append(Issue.title.ilike(f"%{kw}%"))
            conditions.append(Issue.description.ilike(f"%{kw}%"))

        similar = Issue.query.filter(
            Issue.id != issue.id,
            Issue.project_id == issue.project_id,
            or_(*conditions)
        ).order_by(Issue.created_at.desc()).limit(limit).all()

        return similar
