"""Analytics service for system metrics, defect statistics, and reporting."""

from datetime import datetime, timedelta
from sqlalchemy import func, or_
from extensions import db
from models.issue import Issue
from models.project import Project
from models.user import User
from models.sprint import Sprint


class AnalyticsService:
    """Calculates defect metrics and analytics from persisted database records."""

    @staticmethod
    def get_overview_stats(project_id=None):
        """Get aggregate counts for dashboard KPI cards."""
        query = Issue.query
        if project_id:
            query = query.filter(Issue.project_id == project_id)

        total = query.count()
        open_count = query.filter(Issue.status.in_(Issue.OPEN_STATUSES)).count()
        critical = query.filter(Issue.severity == Issue.SEV_CRITICAL, Issue.status.in_(Issue.OPEN_STATUSES)).count()
        awaiting_qa = query.filter(Issue.status == Issue.STATUS_QA_VERIFICATION).count()
        resolved = query.filter(Issue.status == Issue.STATUS_RESOLVED).count()
        closed = query.filter(Issue.status == Issue.STATUS_CLOSED).count()

        active_projects = Project.query.filter_by(status=Project.STATUS_ACTIVE).count()
        active_users = User.query.filter_by(is_active=True).count()

        return {
            'total_issues': total,
            'open_issues': open_count,
            'critical_issues': critical,
            'awaiting_verification': awaiting_qa,
            'resolved_issues': resolved,
            'closed_issues': closed,
            'active_projects': active_projects,
            'active_users': active_users,
        }

    @staticmethod
    def get_status_distribution(project_id=None):
        """Return distribution of issues by status."""
        query = db.session.query(
            Issue.status, func.count(Issue.id)
        )
        if project_id:
            query = query.filter(Issue.project_id == project_id)
        results = query.group_by(Issue.status).all()

        # Format labels nicely
        labels = [status.replace('_', ' ').title() for status, _ in results]
        values = [count for _, count in results]
        raw = [{'status': s, 'count': c, 'label': s.replace('_', ' ').title()} for s, c in results]
        return {'labels': labels, 'values': values, 'raw': raw}

    @staticmethod
    def get_severity_distribution(project_id=None):
        """Return distribution of issues by severity."""
        query = db.session.query(
            Issue.severity, func.count(Issue.id)
        )
        if project_id:
            query = query.filter(Issue.project_id == project_id)
        results = query.group_by(Issue.severity).all()

        labels = [sev.title() for sev, _ in results]
        values = [count for _, count in results]
        raw = [{'severity': s, 'count': c, 'label': s.title()} for s, c in results]
        return {'labels': labels, 'values': values, 'raw': raw}

    @staticmethod
    def get_category_distribution(project_id=None):
        """Return distribution of issues by category."""
        query = db.session.query(
            Issue.category, func.count(Issue.id)
        )
        if project_id:
            query = query.filter(Issue.project_id == project_id)
        results = query.group_by(Issue.category).all()

        labels = [cat.replace('_', ' ').title() if cat else 'Other' for cat, _ in results]
        values = [count for _, count in results]
        raw = [{'category': c, 'count': cnt, 'label': (c or 'other').replace('_', ' ').title()} for c, cnt in results]
        return {'labels': labels, 'values': values, 'raw': raw}

    @staticmethod
    def get_issues_over_time(project_id=None, days=30):
        """Return counts of issues reported per day over the specified window."""
        start_date = datetime.utcnow() - timedelta(days=days)
        query = db.session.query(
            func.date(Issue.created_at).label('report_date'),
            func.count(Issue.id).label('count')
        ).filter(Issue.created_at >= start_date)

        if project_id:
            query = query.filter(Issue.project_id == project_id)

        results = query.group_by(func.date(Issue.created_at)).order_by('report_date').all()

        date_map = {str(r.report_date): r.count for r in results}
        labels = []
        values = []
        for i in range(days + 1):
            d = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
            labels.append(d)
            values.append(date_map.get(d, 0))

        return {'labels': labels, 'values': values}

    @staticmethod
    def get_resolution_times(project_id=None):
        """Calculate resolution time statistics (in hours) for resolved/closed issues."""
        query = Issue.query.filter(
            Issue.resolved_at.isnot(None),
            Issue.status.in_(['resolved', 'closed'])
        )
        if project_id:
            query = query.filter(Issue.project_id == project_id)

        resolved_issues = query.all()
        if not resolved_issues:
            return {'avg_hours': 0, 'median_hours': 0, 'min_hours': 0, 'max_hours': 0, 'count': 0}

        durations = []
        for issue in resolved_issues:
            if issue.created_at and issue.resolved_at:
                delta = (issue.resolved_at - issue.created_at).total_seconds() / 3600.0
                if delta >= 0:
                    durations.append(delta)

        if not durations:
            return {'avg_hours': 0, 'median_hours': 0, 'min_hours': 0, 'max_hours': 0, 'count': 0}

        durations.sort()
        count = len(durations)
        avg_hours = round(sum(durations) / count, 1)
        median_hours = round(durations[count // 2] if count % 2 == 1 else (durations[count // 2 - 1] + durations[count // 2]) / 2, 1)
        min_hours = round(durations[0], 1)
        max_hours = round(durations[-1], 1)

        return {
            'avg_hours': avg_hours,
            'median_hours': median_hours,
            'min_hours': min_hours,
            'max_hours': max_hours,
            'count': count,
        }

    @staticmethod
    def get_developer_workload(project_id=None):
        """Calculate developer workload breakdown: assigned, in progress, resolved."""
        devs = User.query.filter(User.role.in_(['developer', 'admin']), User.is_active.is_(True)).all()
        workload = []

        for dev in devs:
            q = Issue.query.filter_by(assignee_id=dev.id)
            if project_id:
                q = q.filter(Issue.project_id == project_id)

            assigned = q.filter(Issue.status == Issue.STATUS_ASSIGNED).count()
            in_progress = q.filter(Issue.status.in_([Issue.STATUS_IN_PROGRESS, Issue.STATUS_CODE_REVIEW])).count()
            resolved = q.filter(Issue.status.in_([Issue.STATUS_RESOLVED, Issue.STATUS_CLOSED])).count()
            total_active = assigned + in_progress

            workload.append({
                'user_id': dev.id,
                'name': dev.full_name,
                'assigned': assigned,
                'in_progress': in_progress,
                'resolved': resolved,
                'total_active': total_active,
            })

        workload.sort(key=lambda x: x['total_active'], reverse=True)
        return workload

    @staticmethod
    def get_project_comparison():
        """Compare defect metrics across all active projects."""
        projects = Project.query.filter_by(status=Project.STATUS_ACTIVE).all()
        comparison = []

        for p in projects:
            total = p.issues.count()
            open_count = p.issues.filter(Issue.status.in_(Issue.OPEN_STATUSES)).count()
            critical = p.issues.filter(Issue.severity == Issue.SEV_CRITICAL, Issue.status.in_(Issue.OPEN_STATUSES)).count()
            resolved = p.issues.filter(Issue.status.in_([Issue.STATUS_RESOLVED, Issue.STATUS_CLOSED])).count()
            rate = round((resolved / total * 100), 1) if total > 0 else 0.0

            comparison.append({
                'project_id': p.id,
                'name': p.name,
                'key': p.key,
                'total': total,
                'open': open_count,
                'critical': critical,
                'resolved': resolved,
                'resolution_rate': rate,
            })

        return comparison

    @staticmethod
    def get_backlog_health(project_id=None):
        """Evaluate backlog health indicators based on aging defects and unassigned issues."""
        query = Issue.query.filter(Issue.status.in_(Issue.OPEN_STATUSES))
        if project_id:
            query = query.filter(Issue.project_id == project_id)

        total_open = query.count()
        unassigned = query.filter(Issue.assignee_id.is_(None)).count()
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        aging_count = query.filter(Issue.created_at < seven_days_ago).count()

        health_score = 100
        if total_open > 0:
            unassigned_penalty = (unassigned / total_open) * 40
            aging_penalty = (aging_count / total_open) * 40
            health_score = max(0, round(100 - unassigned_penalty - aging_penalty, 0))

        return {
            'total_open': total_open,
            'unassigned': unassigned,
            'aging_issues': aging_count,
            'health_score': int(health_score),
        }

    @staticmethod
    def get_sprint_metrics(sprint_id):
        """Calculate completion rate and breakdown for a sprint."""
        sprint = Sprint.query.get(sprint_id)
        if not sprint:
            return None

        total = sprint.issues.count()
        completed = sprint.issues.filter(Issue.status.in_(['resolved', 'closed'])).count()
        in_progress = sprint.issues.filter(Issue.status.in_(['in_progress', 'code_review', 'qa_verification'])).count()
        todo = sprint.issues.filter(Issue.status.in_(['reported', 'triaging', 'assigned'])).count()
        rate = round((completed / total * 100), 1) if total > 0 else 0.0

        return {
            'sprint_id': sprint.id,
            'sprint_name': sprint.name,
            'status': sprint.status,
            'total_issues': total,
            'completed': completed,
            'in_progress': in_progress,
            'todo': todo,
            'completion_rate': rate,
        }
