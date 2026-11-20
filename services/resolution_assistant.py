"""Resolution assistant — rule-based debugging and resolution suggestions."""

from services.classification_service import ClassificationService
from services.issue_service import IssueService


class ResolutionAssistant:
    """Provides debugging steps, resolution hints, and related issues."""

    DEBUGGING_STEPS = {
        'ui_ux': [
            "Inspect the element using browser DevTools (F12)",
            "Check for CSS specificity conflicts or missing styles",
            "Verify responsive breakpoints and viewport settings",
            "Test across different browsers (Chrome, Firefox, Safari, Edge)",
            "Check for JavaScript console errors related to DOM manipulation",
            "Validate HTML structure and accessibility attributes",
        ],
        'backend_api': [
            "Check server logs for error stack traces",
            "Verify API endpoint routing and HTTP method",
            "Test with curl or Postman to isolate client vs server issue",
            "Check request/response headers and payload format",
            "Verify authentication tokens and session state",
            "Check for middleware or CORS configuration issues",
        ],
        'database': [
            "Check database connection and credentials",
            "Review the SQL query or ORM operation causing the issue",
            "Look for missing migrations or schema changes",
            "Check for constraint violations (unique, foreign key, not null)",
            "Monitor query performance with EXPLAIN/ANALYZE",
            "Verify transaction isolation and locking behavior",
        ],
        'authentication': [
            "Verify user credentials and account status",
            "Check session/token expiration settings",
            "Review role-based access control configuration",
            "Test with different user roles and permissions",
            "Check for CSRF token issues in forms",
            "Verify password hashing and validation logic",
        ],
        'performance': [
            "Profile the application to identify bottlenecks",
            "Check database query performance (N+1 queries, missing indexes)",
            "Monitor memory usage and potential memory leaks",
            "Review caching strategy and cache hit rates",
            "Check for blocking I/O operations",
            "Load test with realistic data volumes",
        ],
        'security': [
            "Scan for common vulnerabilities (OWASP Top 10)",
            "Check input sanitization and output escaping",
            "Verify authentication and authorization at every endpoint",
            "Review sensitive data handling (passwords, tokens, PII)",
            "Check for secure headers (CSP, X-Frame-Options, etc.)",
            "Audit third-party dependencies for known CVEs",
        ],
        'integration': [
            "Verify external service availability and API version",
            "Check webhook endpoints and payload format",
            "Review retry logic and error handling for external calls",
            "Test with mock services to isolate integration issues",
            "Check rate limits and timeout configurations",
            "Verify authentication credentials for third-party services",
        ],
        'configuration': [
            "Verify environment variables and configuration files",
            "Check for environment-specific settings (dev vs production)",
            "Review deployment scripts and container configurations",
            "Validate file paths and directory permissions",
            "Check for missing or incompatible dependency versions",
            "Review logging configuration and log levels",
        ],
        'other': [
            "Review the full error message and stack trace",
            "Attempt to reproduce the issue consistently",
            "Check recent code changes that may have introduced the issue",
            "Review related test cases for failures",
            "Check system resources (disk space, memory, CPU)",
            "Consult documentation for the affected component",
        ],
    }

    RESOLUTION_HINTS = {
        'ui_ux': [
            "Consider adding CSS reset or normalizing styles",
            "Use flexbox or grid for reliable layout alignment",
            "Add fallback fonts and image placeholders",
            "Implement progressive enhancement for older browsers",
        ],
        'backend_api': [
            "Add proper error handling with meaningful HTTP status codes",
            "Implement request validation middleware",
            "Add logging at critical points in the request pipeline",
            "Consider adding rate limiting for public endpoints",
        ],
        'database': [
            "Add appropriate indexes for frequently queried columns",
            "Use database transactions for multi-step operations",
            "Implement soft deletes to preserve data history",
            "Add database migration scripts for schema changes",
        ],
        'authentication': [
            "Implement account lockout after repeated failed attempts",
            "Use secure password hashing (bcrypt/argon2)",
            "Add multi-factor authentication option",
            "Implement proper session invalidation on logout",
        ],
        'performance': [
            "Implement caching at the application and database levels",
            "Use pagination for large data sets",
            "Optimize database queries and add missing indexes",
            "Consider async processing for heavy operations",
        ],
        'security': [
            "Apply input validation at both client and server side",
            "Use parameterized queries to prevent SQL injection",
            "Implement Content Security Policy headers",
            "Regularly update dependencies to patch known vulnerabilities",
        ],
        'integration': [
            "Implement circuit breaker pattern for external service calls",
            "Add comprehensive error handling for network failures",
            "Use webhook signature verification",
            "Implement idempotency for retry operations",
        ],
        'configuration': [
            "Use environment variables for sensitive configuration",
            "Implement configuration validation at startup",
            "Document all configuration options with defaults",
            "Use feature flags for gradual rollout of changes",
        ],
        'other': [
            "Write or update unit tests covering the affected functionality",
            "Add integration tests for end-to-end verification",
            "Document the root cause and resolution for future reference",
            "Consider adding monitoring or alerting for this scenario",
        ],
    }

    @classmethod
    def get_suggestions(cls, issue):
        """
        Get comprehensive resolution suggestions for an issue.

        Returns dict with classification, debugging steps, hints, and related issues.
        """
        # Get classification
        classification = ClassificationService.classify_issue(
            title=issue.title,
            description=issue.description or '',
            component=issue.component,
            issue_type=issue.issue_type,
        )

        category = issue.category if issue.category != 'other' else classification['suggested_category']

        # Get debugging steps
        debugging_steps = cls.get_debugging_steps(category)

        # Get resolution hints
        resolution_hints = cls.get_resolution_hints(category, issue.severity)

        # Get related issues
        related_issues = IssueService.get_similar_issues(issue, limit=5)

        return {
            'classification': classification,
            'debugging_steps': debugging_steps,
            'resolution_hints': resolution_hints,
            'related_issues': [
                {
                    'issue_key': ri.issue_key,
                    'title': ri.title,
                    'status': ri.status,
                    'severity': ri.severity,
                    'resolution_notes': ri.resolution_notes or '',
                }
                for ri in related_issues
            ],
            'has_suggestions': True,
        }

    @classmethod
    def get_debugging_steps(cls, category):
        """Get debugging steps for a category."""
        return cls.DEBUGGING_STEPS.get(category, cls.DEBUGGING_STEPS['other'])

    @classmethod
    def get_resolution_hints(cls, category, severity=None):
        """Get resolution hints for a category."""
        hints = cls.RESOLUTION_HINTS.get(category, cls.RESOLUTION_HINTS['other'])
        if severity == 'critical':
            hints = ["⚠ CRITICAL: Prioritize immediate investigation and hotfix"] + hints
        return hints
