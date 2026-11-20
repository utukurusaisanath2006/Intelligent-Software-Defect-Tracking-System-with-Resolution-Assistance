"""Database seeding script with realistic defect tracking data."""

from datetime import datetime, timedelta
from extensions import db
from models.user import User
from models.project import Project, ProjectMembership
from models.issue import Issue
from models.comment import Comment
from models.activity import Activity
from models.sprint import Sprint
from models.release import Release
from models.notification import Notification


def seed_database():
    """Populate database with demo users, projects, issues, and audit records."""

    # 1. Create Users
    users_data = [
        {
            'username': 'admin',
            'email': 'admin@intellitrack.dev',
            'password': 'admin123',
            'first_name': 'Eleanor',
            'last_name': 'Vance',
            'role': User.ROLE_ADMIN,
        },
        {
            'username': 'dev_marcus',
            'email': 'dev@intellitrack.dev',
            'password': 'dev123',
            'first_name': 'Marcus',
            'last_name': 'Chen',
            'role': User.ROLE_DEVELOPER,
        },
        {
            'username': 'dev_sarah',
            'email': 'sarah@intellitrack.dev',
            'password': 'dev123',
            'first_name': 'Sarah',
            'last_name': 'Kovacs',
            'role': User.ROLE_DEVELOPER,
        },
        {
            'username': 'reporter_alex',
            'email': 'reporter@intellitrack.dev',
            'password': 'reporter123',
            'first_name': 'Alex',
            'last_name': 'Rivera',
            'role': User.ROLE_REPORTER,
        },
    ]

    users = {}
    for udata in users_data:
        existing = User.query.filter_by(email=udata['email']).first()
        if not existing:
            user = User(
                username=udata['username'],
                email=udata['email'],
                first_name=udata['first_name'],
                last_name=udata['last_name'],
                role=udata['role'],
                is_active=True,
                created_at=datetime.utcnow() - timedelta(days=60)
            )
            user.set_password(udata['password'])
            db.session.add(user)
            db.session.flush()
            users[udata['username']] = user
        else:
            users[udata['username']] = existing

    admin_user = users['admin']
    dev1 = users['dev_marcus']
    dev2 = users['dev_sarah']
    reporter = users['reporter_alex']

    # 2. Create Projects
    projects_data = [
        {
            'name': 'E-Commerce Platform',
            'key': 'ECOM',
            'description': 'High-throughput online storefront, catalog search, cart engine, and payment checkout integrations.',
        },
        {
            'name': 'Mobile Banking App',
            'key': 'MOBI',
            'description': 'Cross-platform iOS and Android retail mobile application with biometric login and instant transfers.',
        },
        {
            'name': 'Cloud API Gateway',
            'key': 'APIG',
            'description': 'Distributed edge proxy providing API authentication, rate limiting, request routing, and metric telemetry.',
        },
    ]

    projects = {}
    for pdata in projects_data:
        existing = Project.query.filter_by(key=pdata['key']).first()
        if not existing:
            proj = Project(
                name=pdata['name'],
                key=pdata['key'],
                description=pdata['description'],
                status=Project.STATUS_ACTIVE,
                created_at=datetime.utcnow() - timedelta(days=45)
            )
            db.session.add(proj)
            db.session.flush()
            projects[pdata['key']] = proj

            # Add memberships
            for u in [admin_user, dev1, dev2, reporter]:
                m = ProjectMembership(user_id=u.id, project_id=proj.id, role='member')
                db.session.add(m)
        else:
            projects[pdata['key']] = existing

    # 3. Create Sprints
    ecom = projects['ECOM']
    mobi = projects['MOBI']

    sprint1 = Sprint.query.filter_by(name='Sprint 14 - Checkout Hardening', project_id=ecom.id).first()
    if not sprint1:
        sprint1 = Sprint(
            name='Sprint 14 - Checkout Hardening',
            project_id=ecom.id,
            status=Sprint.STATUS_ACTIVE,
            start_date=(datetime.utcnow() - timedelta(days=7)).date(),
            end_date=(datetime.utcnow() + timedelta(days=7)).date(),
            goal='Eliminate payment edge-case timeouts and resolve session desynchronization during peak load.'
        )
        db.session.add(sprint1)

    sprint2 = Sprint.query.filter_by(name='Sprint 08 - Biometric Auth Revamp', project_id=mobi.id).first()
    if not sprint2:
        sprint2 = Sprint(
            name='Sprint 08 - Biometric Auth Revamp',
            project_id=mobi.id,
            status=Sprint.STATUS_ACTIVE,
            start_date=(datetime.utcnow() - timedelta(days=4)).date(),
            end_date=(datetime.utcnow() + timedelta(days=10)).date(),
            goal='Upgrade FaceID and fingerprint validation with fallback passphrase challenge.'
        )
        db.session.add(sprint2)
    db.session.flush()

    # 4. Create Releases
    rel1 = Release.query.filter_by(version='v2.4.0', project_id=ecom.id).first()
    if not rel1:
        rel1 = Release(
            name='Q1 Core Services Update',
            version='v2.4.0',
            project_id=ecom.id,
            status=Release.STATUS_IN_PROGRESS,
            release_date=(datetime.utcnow() + timedelta(days=14)).date(),
            description='Includes unified cart checkout, payment webhook retry logic, and inventory locking.'
        )
        db.session.add(rel1)
        db.session.flush()

    # 5. Create Issues if not already seeded
    if Issue.query.count() == 0:
        issues_def = [
            {
                'project': ecom,
                'key': 'ECOM-1',
                'title': 'Race condition during multi-item inventory deduction during flash sales',
                'description': 'Concurrent requests for the final available stock unit result in negative inventory balances because quantity checks are not locked atomically inside the checkout transaction.',
                'type': Issue.TYPE_BUG,
                'category': 'database',
                'severity': Issue.SEV_CRITICAL,
                'priority': Issue.PRI_URGENT,
                'status': Issue.STATUS_IN_PROGRESS,
                'component': 'Inventory & Checkout',
                'environment': 'Production (Staging verified)',
                'steps': '1. Seed item inventory with quantity = 1.\n2. Fire 10 parallel HTTP POST /api/checkout requests within 50ms.\n3. Inspect inventory balance in database.',
                'expected': 'Exactly 1 transaction succeeds; remaining 9 receive HTTP 409 Out of Stock.',
                'actual': '3 transactions succeed and inventory counter updates to -2.',
                'root_cause': 'Read-modify-write pattern executed without SELECT FOR UPDATE row locking.',
                'res_notes': 'Refactored inventory decrement to use atomic conditional update with row level locks.',
                'reporter': reporter,
                'assignee': dev1,
                'sprint': sprint1,
                'created_delta': 5,
            },
            {
                'project': ecom,
                'key': 'ECOM-2',
                'title': 'Stripe webhook payment confirmation signature verification fails on payload encoding',
                'description': 'Incoming Stripe webhook events intermittently trigger HTTP 400 signature verification errors due to UTF-8 raw buffer truncation before crypto validation.',
                'type': Issue.TYPE_BUG,
                'category': 'security',
                'severity': Issue.SEV_CRITICAL,
                'priority': Issue.PRI_HIGH,
                'status': Issue.STATUS_QA_VERIFICATION,
                'component': 'Payment Gateway',
                'environment': 'Staging Sandbox',
                'steps': '1. Trigger Stripe charge.succeeded webhook containing UTF-8 customer name.\n2. Observe gateway logs at /webhook/stripe.',
                'expected': 'Signature verified, webhook returns 200, order status updated to PAID.',
                'actual': 'Signature verification exception raised; webhook returns 400 Bad Request.',
                'root_cause': 'Request body was decoded as ASCII prior to HMAC calculation.',
                'res_notes': 'Preserved request.get_data(as_text=False) raw bytes directly for HMAC-SHA256 signature check.',
                'reporter': reporter,
                'assignee': dev2,
                'sprint': sprint1,
                'created_delta': 8,
                'resolved_delta': 1,
            },
            {
                'project': ecom,
                'key': 'ECOM-3',
                'title': 'Product catalog filter drawer button unresponsive on mobile viewport (width < 375px)',
                'description': 'On small screens like iPhone SE, clicking the "Filter Products" button does not open the drawer because of a z-index overlay collision with the fixed bottom cart bar.',
                'type': Issue.TYPE_BUG,
                'category': 'ui_ux',
                'severity': Issue.SEV_MINOR,
                'priority': Issue.PRI_MEDIUM,
                'status': Issue.STATUS_RESOLVED,
                'component': 'Catalog UI',
                'environment': 'Mobile Safari 17.2, Chrome Mobile 120',
                'steps': '1. Open /catalog on viewport 320x568.\n2. Tap the "Filter" pill button.\n3. Observe nothing happens.',
                'expected': 'Slide-over drawer animates from right edge showing facet filters.',
                'actual': 'Tap target is intercepted by transparent pseudo-element of sticky cart bar.',
                'root_cause': 'CSS z-index conflict on .bottom-cart-bar wrapper.',
                'res_notes': 'Set pointer-events: none on wrapper and explicit z-index: 100 on filter toggle button.',
                'reporter': reporter,
                'assignee': dev1,
                'sprint': sprint1,
                'created_delta': 12,
                'resolved_delta': 4,
            },
            {
                'project': ecom,
                'key': 'ECOM-4',
                'title': 'Implement automated order confirmation email retry queue with exponential backoff',
                'description': 'Add dead-letter retry mechanism when third-party transactional mail API experiences transient 5xx outages.',
                'type': Issue.TYPE_ENHANCEMENT,
                'category': 'integration',
                'severity': Issue.SEV_MAJOR,
                'priority': Issue.PRI_HIGH,
                'status': Issue.STATUS_CODE_REVIEW,
                'component': 'Notification Worker',
                'environment': 'All environments',
                'steps': 'Trigger 50 orders while simulating SendGrid downtime.',
                'expected': 'Failed notifications enter retry queue with exponential delays (1m, 5m, 15m).',
                'actual': 'Notifications fail once and are permanently dropped.',
                'root_cause': 'No persistent retry queue implemented in worker dispatch.',
                'res_notes': 'Introduced database backed retry attempts with backoff intervals.',
                'reporter': admin_user,
                'assignee': dev2,
                'sprint': sprint1,
                'created_delta': 6,
            },
            {
                'project': ecom,
                'key': 'ECOM-5',
                'title': 'Memory consumption spike during bulk CSV price update export for 50,000+ SKUs',
                'description': 'Generating large catalog CSV export loads all SQLAlchemy models into memory at once instead of batching or streaming records.',
                'type': Issue.TYPE_BUG,
                'category': 'performance',
                'severity': Issue.SEV_MAJOR,
                'priority': Issue.PRI_HIGH,
                'status': Issue.STATUS_ASSIGNED,
                'component': 'Merchant Admin',
                'environment': 'Staging',
                'steps': '1. Navigate to Admin -> Bulk Catalog Export.\n2. Select Full Catalog (52,000 items).\n3. Click Export CSV.',
                'expected': 'Export downloads smoothly via chunked streaming response.',
                'actual': 'Worker memory reaches 1.8GB and OOM killer terminates process.',
                'root_cause': 'db.session.query(Product).all() used instead of yield_per(1000).',
                'res_notes': '',
                'reporter': reporter,
                'assignee': dev1,
                'sprint': None,
                'created_delta': 4,
            },
            {
                'project': mobi,
                'key': 'MOBI-1',
                'title': 'Biometric FaceID authentication prompt crashes immediately after background resume',
                'description': 'Resuming the application from background while biometric prompt was active throws unhandled NSNull pointer exception in biometric bridge module.',
                'type': Issue.TYPE_BUG,
                'category': 'authentication',
                'severity': Issue.SEV_CRITICAL,
                'priority': Issue.PRI_URGENT,
                'status': Issue.STATUS_IN_PROGRESS,
                'component': 'Security Bridge',
                'environment': 'iOS 17.4 Simulator & Physical iPhone 14',
                'steps': '1. Trigger transfer requiring FaceID.\n2. While prompt is displayed, press Home to send app to background.\n3. Resume app from app switcher.',
                'expected': 'Biometric prompt gracefully cancels or resets cleanly.',
                'actual': 'App crashes with EXC_BAD_ACCESS in NativeAuthBridge.swift:142.',
                'root_cause': 'Context delegate invalidated when app lifecycle state changed to background.',
                'res_notes': 'Added lifecycle listener to dismiss LAContext gracefully before suspension.',
                'reporter': reporter,
                'assignee': dev2,
                'sprint': sprint2,
                'created_delta': 7,
            },
            {
                'project': mobi,
                'key': 'MOBI-2',
                'title': 'Recent transaction list displays unescaped payee strings causing visual formatting glitch',
                'description': 'Special characters such as ampersands and angle brackets in merchant names are rendered literally, disrupting list item alignment.',
                'type': Issue.TYPE_BUG,
                'category': 'ui_ux',
                'severity': Issue.SEV_MINOR,
                'priority': Issue.PRI_LOW,
                'status': Issue.STATUS_REPORTED,
                'component': 'Dashboard Feed',
                'environment': 'Android 14 (Pixel 7)',
                'steps': '1. Transfer funds to payee with name "A&B <Electronics> Ltd".\n2. Open dashboard transaction history.',
                'expected': 'Merchant name cleanly sanitized and displayed.',
                'actual': 'Angle brackets break item card text bounding box.',
                'root_cause': 'Missing text escape filter in custom list cell renderer.',
                'res_notes': '',
                'reporter': reporter,
                'assignee': None,
                'sprint': sprint2,
                'created_delta': 2,
            },
            {
                'project': mobi,
                'key': 'MOBI-3',
                'title': 'Session token refresh endpoint returns HTTP 401 on fast successive network switches',
                'description': 'Switching between WiFi and Cellular during an active session invalidates refresh tokens due to strict IP binding without grace period.',
                'type': Issue.TYPE_BUG,
                'category': 'authentication',
                'severity': Issue.SEV_MAJOR,
                'priority': Issue.PRI_HIGH,
                'status': Issue.STATUS_TRIAGING,
                'component': 'Token Service',
                'environment': 'LTE / 5G / WiFi roaming',
                'steps': '1. Authenticate on WiFi.\n2. Disable WiFi to roam to LTE while app performs background sync.\n3. Observe refresh token rejection.',
                'expected': 'Refresh token accepted within 30-second roaming window with valid device fingerprint.',
                'actual': 'User forcefully logged out with session expired banner.',
                'root_cause': 'Token validation requires identical client IP address without tolerance for mobile subnet hopping.',
                'res_notes': '',
                'reporter': reporter,
                'assignee': None,
                'sprint': None,
                'created_delta': 3,
            },
            {
                'project': mobi,
                'key': 'MOBI-4',
                'title': 'Support dark mode color scheme across account statement PDF generator',
                'description': 'Account statement export is illegible when exported in device dark theme because background stays white while fonts invert.',
                'type': Issue.TYPE_ENHANCEMENT,
                'category': 'ui_ux',
                'severity': Issue.SEV_MINOR,
                'priority': Issue.PRI_LOW,
                'status': Issue.STATUS_CLOSED,
                'component': 'Reporting Module',
                'environment': 'iOS & Android',
                'steps': 'Export monthly PDF statement while device is in system dark mode.',
                'expected': 'Clean printable document with consistent high-contrast colors.',
                'actual': 'White text on white background rendered in PDF view.',
                'root_cause': 'PDF template inherited CSS media (prefers-color-scheme: dark).',
                'res_notes': 'Forced print media styles with explicit white page and ink-charcoal text.',
                'reporter': reporter,
                'assignee': dev1,
                'sprint': None,
                'created_delta': 20,
                'resolved_delta': 15,
            },
            {
                'project': projects['APIG'],
                'key': 'APIG-1',
                'title': 'Redis cluster failover triggers 15-second connection timeout storm on edge proxy',
                'description': 'When Redis primary promotes a replica, edge proxy connection pool does not invalidate stale socket connections promptly, stalling incoming HTTP requests.',
                'type': Issue.TYPE_BUG,
                'category': 'performance',
                'severity': Issue.SEV_CRITICAL,
                'priority': Issue.PRI_URGENT,
                'status': Issue.STATUS_IN_PROGRESS,
                'component': 'Proxy Cache Layer',
                'environment': 'Staging Cluster',
                'steps': '1. Run load test generating 2,000 req/sec through gateway.\n2. Initiate Redis failover via cluster failover command.\n3. Measure edge proxy latency percentile.',
                'expected': 'P99 latency increases by max 250ms during topology reconfiguration.',
                'actual': 'Requests hang for 15s before socket timeout drops connections.',
                'root_cause': 'Socket read timeout default set to 15000ms instead of 800ms with retry.',
                'res_notes': 'Configured dynamic health check probe and reduced socket timeout to 500ms.',
                'reporter': admin_user,
                'assignee': dev1,
                'sprint': None,
                'created_delta': 9,
            },
            {
                'project': projects['APIG'],
                'key': 'APIG-2',
                'title': 'Rate limiter sliding window counter leaks memory when keys exceed 100,000 clients',
                'description': 'Sorted set timestamp members in Redis are pruned only on key hits, leaving abandoned IP keys in memory indefinitely without TTL expiration.',
                'type': Issue.TYPE_BUG,
                'category': 'backend_api',
                'severity': Issue.SEV_MAJOR,
                'priority': Issue.PRI_HIGH,
                'status': Issue.STATUS_QA_VERIFICATION,
                'component': 'Rate Limiter Service',
                'environment': 'Production telemetry',
                'steps': 'Simulate 200,000 unique client IP addresses sending 1 request each.',
                'expected': 'Keys automatically expire after the 60-second window.',
                'actual': 'Redis memory grows continuously; keys have no EXPIRE directive set.',
                'root_cause': 'ZADD pipeline omitted EXPIRE key 120 command.',
                'res_notes': 'Added atomic EXPIRE 120 to pipeline execution on every sliding window evaluation.',
                'reporter': reporter,
                'assignee': dev2,
                'sprint': None,
                'created_delta': 10,
                'resolved_delta': 2,
            },
            {
                'project': projects['APIG'],
                'key': 'APIG-3',
                'title': 'Refactor OAuth2 introspection token caching to utilize SHA-256 digest keys',
                'description': 'Currently raw bearer tokens are stored as Redis cache keys, exposing active tokens in Redis monitoring logs.',
                'type': Issue.TYPE_TECHNICAL_DEBT,
                'category': 'security',
                'severity': Issue.SEV_MAJOR,
                'priority': Issue.PRI_HIGH,
                'status': Issue.STATUS_RESOLVED,
                'component': 'Auth Introspect Module',
                'environment': 'All environments',
                'steps': 'Inspect Redis keyspace using redis-cli MONITOR during authenticated API calls.',
                'expected': 'Keys are opaque SHA-256 hashes.',
                'actual': 'Plaintext bearer tokens visible in redis commands.',
                'root_cause': 'Cache key constructed as f"token:{raw_token}".',
                'res_notes': 'Updated key generation to f"token:{hashlib.sha256(raw_token.encode()).hexdigest()}".',
                'reporter': admin_user,
                'assignee': dev1,
                'sprint': None,
                'created_delta': 15,
                'resolved_delta': 8,
            },
            {
                'project': projects['APIG'],
                'key': 'APIG-4',
                'title': 'Allow route level CORS preflight cache duration configuration',
                'description': 'Expose Access-Control-Max-Age configuration per route to optimize preflight OPTIONS traffic from browser clients.',
                'type': Issue.TYPE_FEATURE,
                'category': 'configuration',
                'severity': Issue.SEV_MINOR,
                'priority': Issue.PRI_LOW,
                'status': Issue.STATUS_REPORTED,
                'component': 'Routing Engine',
                'environment': 'Development',
                'steps': 'Configure route with cors_max_age = 86400 and send OPTIONS request.',
                'expected': 'Response header contains Access-Control-Max-Age: 86400.',
                'actual': 'Hardcoded value of 3600 is returned.',
                'root_cause': 'Route YAML schema lacks cors_max_age parameter.',
                'res_notes': '',
                'reporter': reporter,
                'assignee': None,
                'sprint': None,
                'created_delta': 1,
            },
        ]

        created_issues = []
        for idata in issues_def:
            c_time = datetime.utcnow() - timedelta(days=idata['created_delta'])
            r_time = datetime.utcnow() - timedelta(days=idata.get('resolved_delta', 0)) if idata.get('resolved_delta') else None

            issue = Issue(
                issue_key=idata['key'],
                title=idata['title'],
                description=idata['description'],
                issue_type=idata['type'],
                category=idata['category'],
                severity=idata['severity'],
                priority=idata['priority'],
                status=idata['status'],
                component=idata['component'],
                environment=idata['environment'],
                steps_to_reproduce=idata['steps'],
                expected_result=idata['expected'],
                actual_result=idata['actual'],
                root_cause=idata['root_cause'],
                resolution_notes=idata['res_notes'],
                project_id=idata['project'].id,
                reporter_id=idata['reporter'].id,
                assignee_id=idata['assignee'].id if idata['assignee'] else None,
                sprint_id=idata['sprint'].id if idata.get('sprint') else None,
                release_id=rel1.id if idata['project'].id == ecom.id else None,
                created_at=c_time,
                updated_at=r_time or c_time,
                resolved_at=r_time,
            )
            db.session.add(issue)
            db.session.flush()
            created_issues.append(issue)

            # Add creation activity
            act1 = Activity(
                issue_id=issue.id,
                project_id=issue.project_id,
                actor_id=idata['reporter'].id,
                event_type=Activity.EVT_CREATED,
                details=f"Issue {issue.issue_key} reported by {idata['reporter'].full_name}",
                created_at=c_time,
            )
            db.session.add(act1)

            # Add status/assignment activity if assigned
            if idata['assignee']:
                act2 = Activity(
                    issue_id=issue.id,
                    project_id=issue.project_id,
                    actor_id=admin_user.id,
                    event_type=Activity.EVT_ASSIGNED,
                    field_name='assignee',
                    old_value='Unassigned',
                    new_value=idata['assignee'].full_name,
                    details=f"Assigned to {idata['assignee'].full_name}",
                    created_at=c_time + timedelta(hours=2),
                )
                db.session.add(act2)

            if idata['status'] in ['in_progress', 'code_review', 'qa_verification', 'resolved', 'closed']:
                act3 = Activity(
                    issue_id=issue.id,
                    project_id=issue.project_id,
                    actor_id=idata['assignee'].id if idata['assignee'] else admin_user.id,
                    event_type=Activity.EVT_STATUS_CHANGED,
                    field_name='status',
                    old_value='assigned',
                    new_value=idata['status'],
                    details=f"Work transitioned to {idata['status'].replace('_', ' ').title()}",
                    created_at=c_time + timedelta(hours=8),
                )
                db.session.add(act3)

        # 6. Add Comments to Issues
        if created_issues:
            c1 = Comment(
                issue_id=created_issues[0].id,
                author_id=dev1.id,
                body="I reproduced the negative balance in staging with 10 concurrent requests. The problem is indeed in the inventory decrement transaction. Working on applying a row lock via SELECT FOR UPDATE.",
                created_at=datetime.utcnow() - timedelta(days=4)
            )
            c2 = Comment(
                issue_id=created_issues[0].id,
                author_id=reporter.id,
                body="Thanks Marcus! Please ensure that when the row lock is held, the query timeout doesn't exceed 2 seconds to avoid connection pool exhaustion.",
                created_at=datetime.utcnow() - timedelta(days=3)
            )
            c3 = Comment(
                issue_id=created_issues[1].id,
                author_id=dev2.id,
                body="Fix deployed to staging environment. Webhook HMAC test suite is now passing with diverse unicode names.",
                created_at=datetime.utcnow() - timedelta(days=1)
            )
            db.session.add_all([c1, c2, c3])

        # 7. Add Notifications
        n1 = Notification(
            user_id=dev1.id,
            issue_id=created_issues[0].id,
            type=Notification.TYPE_ASSIGNED,
            message=f"You have been assigned to critical bug {created_issues[0].issue_key}",
            is_read=False,
            created_at=datetime.utcnow() - timedelta(hours=3)
        )
        n2 = Notification(
            user_id=reporter.id,
            issue_id=created_issues[1].id,
            type=Notification.TYPE_STATUS_CHANGED,
            message=f"{created_issues[1].issue_key} is ready for QA Verification",
            is_read=False,
            created_at=datetime.utcnow() - timedelta(hours=5)
        )
        n3 = Notification(
            user_id=admin_user.id,
            issue_id=created_issues[0].id,
            type=Notification.TYPE_INFO,
            message="Critical defect ECOM-1 reported in E-Commerce Platform",
            is_read=True,
            created_at=datetime.utcnow() - timedelta(days=2)
        )
        db.session.add_all([n1, n2, n3])

    db.session.commit()
    print("Database seeding completed.")
