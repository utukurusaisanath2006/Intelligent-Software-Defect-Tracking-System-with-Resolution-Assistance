"""Authentication routes for login, logout, and registration."""

import time
from collections import defaultdict
from threading import Lock
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from models.user import User
from extensions import db

auth_bp = Blueprint('auth', __name__)


class LoginRateLimiter:
    """Sliding-window IP rate limiter to defend against brute-force password attacks."""
    def __init__(self):
        self._attempts = defaultdict(list)
        self._lock = Lock()

    def is_limited(self, ip_address, max_attempts=5, window_seconds=60):
        now = time.time()
        with self._lock:
            self._attempts[ip_address] = [t for t in self._attempts[ip_address] if now - t < window_seconds]
            if len(self._attempts[ip_address]) >= max_attempts:
                return True
            self._attempts[ip_address].append(now)
            return False

    def reset(self, ip_address):
        with self._lock:
            self._attempts.pop(ip_address, None)


login_limiter = LoginRateLimiter()


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page."""
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.overview'))
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        client_ip = request.remote_addr or '127.0.0.1'
        # Check rate limiting (disabled during standard automated test runs unless explicitly tested)
        is_testing = current_app.config.get('TESTING', False) and not request.headers.get('X-Test-Rate-Limit')
        if not is_testing and login_limiter.is_limited(client_ip, max_attempts=5, window_seconds=60):
            current_app.logger.warning(f"Security Alert: Rate limit exceeded on /auth/login from ip={client_ip}")
            flash('Too many login attempts. Please wait 1 minute before trying again.', 'error')
            return render_template('auth/login.html'), 429

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        if not email or not password:
            flash('Please provide both email and password.', 'error')
            return render_template('auth/login.html')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if not user.is_active:
                current_app.logger.warning(f"Security Alert: Deactivated user '{email}' attempted login from ip={client_ip}")
                flash('Your account has been deactivated. Please contact an administrator.', 'error')
                return render_template('auth/login.html')

            login_limiter.reset(client_ip)
            login_user(user, remember=remember)
            current_app.logger.info(f"User '{user.username}' successfully authenticated from ip={client_ip}")
            flash(f'Welcome back, {user.full_name}!', 'success')

            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)

            if user.is_admin:
                return redirect(url_for('admin.overview'))
            return redirect(url_for('dashboard.index'))
        else:
            current_app.logger.warning(f"Security Alert: Failed login attempt for email='{email}' from ip={client_ip}")
            flash('Invalid email address or password.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        if not username or not email or not password:
            flash('Username, email, and password are required.', 'error')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('An account with this email address already exists.', 'error')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('This username is already taken.', 'error')
            return render_template('auth/register.html')

        # Public self-registration strictly assigns the reporter role.
        # Any role parameter submitted by the client is ignored to prevent privilege escalation.
        role = User.ROLE_REPORTER

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Your account has been registered. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Log out current user."""
    logout_user()
    flash('You have been logged out securely.', 'info')
    return redirect(url_for('auth.login'))
