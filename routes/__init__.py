"""Routes blueprint registration."""

def register_blueprints(app):
    """Register all Flask blueprints with the application."""
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.issues import issues_bp
    from routes.projects import projects_bp
    from routes.admin import admin_bp
    from routes.sprints import sprints_bp
    from routes.releases import releases_bp
    from routes.api import api_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(issues_bp, url_prefix='/issues')
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(sprints_bp, url_prefix='/sprints')
    app.register_blueprint(releases_bp, url_prefix='/releases')
    app.register_blueprint(api_bp, url_prefix='/api/v1')
