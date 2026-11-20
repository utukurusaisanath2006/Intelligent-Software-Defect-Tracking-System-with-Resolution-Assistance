"""Classification service — rule-based issue categorization and prioritization."""


class ClassificationService:
    """Deterministic, explainable issue classification."""

    CATEGORY_KEYWORDS = {
        'ui_ux': ['button', 'layout', 'css', 'display', 'responsive', 'font', 'color',
                  'ui', 'ux', 'modal', 'form', 'render', 'style', 'alignment', 'visual',
                  'screen', 'page', 'view', 'icon', 'image', 'menu', 'navigation', 'tooltip'],
        'backend_api': ['api', 'endpoint', 'server', 'request', 'response', 'rest', 'route',
                        'controller', '500', '503', '404', 'backend', 'service', 'handler',
                        'middleware', 'cors', 'header', 'payload', 'json'],
        'database': ['database', 'query', 'sql', 'migration', 'table', 'record', 'index',
                     'join', 'orm', 'schema', 'column', 'constraint', 'transaction', 'deadlock',
                     'connection pool', 'sqlite', 'postgres'],
        'authentication': ['login', 'password', 'auth', 'session', 'token', 'permission',
                          'role', 'access', 'logout', 'register', 'credential', 'oauth',
                          'jwt', 'unauthorized', '401', '403', 'forbidden'],
        'performance': ['slow', 'timeout', 'memory', 'cpu', 'load', 'latency', 'cache',
                       'optimize', 'performance', 'lag', 'delay', 'bottleneck', 'throughput',
                       'resource', 'leak', 'profil'],
        'security': ['vulnerability', 'injection', 'xss', 'csrf', 'encrypt', 'ssl',
                    'certificate', 'security', 'exploit', 'attack', 'breach', 'sanitiz',
                    'escape', 'malicious', 'cve'],
        'integration': ['webhook', 'third-party', 'integration', 'sync', 'external', 'plugin',
                       'connector', 'api call', 'callback', 'import', 'export', 'feed'],
        'configuration': ['config', 'setting', 'environment', 'variable', 'deploy', 'setup',
                          'install', 'docker', 'yml', 'yaml', 'properties', 'env'],
    }

    SEVERITY_KEYWORDS = {
        'critical': ['crash', 'data loss', 'security breach', 'system down', 'cannot access',
                    'production', 'outage', 'corrupt', 'unrecoverable', 'blocked', 'fatal',
                    'complete failure', 'all users affected'],
        'major': ['broken', 'error', 'fail', 'incorrect', 'wrong', 'missing data',
                 'not working', 'exception', 'cannot', 'unable', 'regression', 'significant'],
        'minor': ['slow', 'unclear', 'confusing', 'minor', 'cosmetic', 'typo',
                 'inconsistent', 'slight', 'occasionally', 'workaround available'],
        'trivial': ['enhancement', 'nice to have', 'improvement', 'cleanup',
                   'documentation', 'refactor', 'polish', 'suggestion'],
    }

    PRIORITY_MATRIX = {
        # (severity, type) -> priority
        ('critical', 'bug'): 'urgent',
        ('critical', 'feature'): 'high',
        ('critical', 'enhancement'): 'high',
        ('critical', 'technical_debt'): 'high',
        ('major', 'bug'): 'high',
        ('major', 'feature'): 'medium',
        ('major', 'enhancement'): 'medium',
        ('major', 'technical_debt'): 'medium',
        ('minor', 'bug'): 'medium',
        ('minor', 'feature'): 'low',
        ('minor', 'enhancement'): 'low',
        ('minor', 'technical_debt'): 'low',
        ('trivial', 'bug'): 'low',
        ('trivial', 'feature'): 'low',
        ('trivial', 'enhancement'): 'low',
        ('trivial', 'technical_debt'): 'low',
    }

    @classmethod
    def classify_issue(cls, title, description, component=None, issue_type='bug'):
        """
        Classify an issue based on text analysis.

        Returns dict with suggestions and explanations.
        """
        text = f"{title} {description} {component or ''}".lower()

        # Category classification
        category_scores = {}
        for cat, keywords in cls.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                category_scores[cat] = score

        if category_scores:
            suggested_category = max(category_scores, key=category_scores.get)
            max_score = category_scores[suggested_category]
            total_keywords = len(cls.CATEGORY_KEYWORDS[suggested_category])
            confidence = min(round((max_score / max(total_keywords * 0.3, 1)) * 100, 0), 95)
            matched = [kw for kw in cls.CATEGORY_KEYWORDS[suggested_category] if kw in text]
            category_reason = f"Matched keywords: {', '.join(matched[:5])}"
        else:
            suggested_category = 'other'
            confidence = 20
            category_reason = "No strong keyword matches found"

        # Severity classification
        severity_scores = {}
        for sev, keywords in cls.SEVERITY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                severity_scores[sev] = score

        if severity_scores:
            suggested_severity = max(severity_scores, key=severity_scores.get)
            matched_sev = [kw for kw in cls.SEVERITY_KEYWORDS[suggested_severity] if kw in text]
            severity_reason = f"Severity indicators found: {', '.join(matched_sev[:4])}"
        else:
            suggested_severity = 'minor'
            severity_reason = "No specific severity indicators detected; defaulting to minor"

        # Priority from matrix
        suggested_priority = cls.get_priority_from_severity(suggested_severity, issue_type)
        priority_reason = f"Based on {suggested_severity} severity and {issue_type} type"

        return {
            'suggested_category': suggested_category,
            'category_confidence': confidence,
            'category_reason': category_reason,
            'suggested_severity': suggested_severity,
            'severity_reason': severity_reason,
            'suggested_priority': suggested_priority,
            'priority_reason': priority_reason,
        }

    @classmethod
    def get_priority_from_severity(cls, severity, issue_type='bug'):
        """Derive priority from severity and issue type using the priority matrix."""
        return cls.PRIORITY_MATRIX.get((severity, issue_type), 'medium')
