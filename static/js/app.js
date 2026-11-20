/**
 * IntelliTrack Core Application Script
 * Handles navigation drawer, global search, notifications, dropdowns, and toasts.
 */

(function () {
  'use strict';

  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }
  window.getCsrfToken = getCsrfToken;

  function debounce(fn, delay) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  window.showToast = function (message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${escapeHtml(message)}</span><button class="toast-close" aria-label="Dismiss">&times;</button>`;
    toast.querySelector('.toast-close').addEventListener('click', () => toast.remove());
    container.appendChild(toast);
    if (duration > 0) {
      setTimeout(() => toast.remove(), duration);
    }
  };

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  document.addEventListener('DOMContentLoaded', () => {
    // 1. Mobile Sidebar Drawer
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    function closeSidebar() {
      if (sidebar) sidebar.classList.remove('open');
      if (sidebarOverlay) sidebarOverlay.classList.remove('open');
    }

    if (sidebarToggle && sidebar) {
      sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('open');
        if (sidebarOverlay) sidebarOverlay.classList.toggle('open');
      });
    }
    if (sidebarOverlay) {
      sidebarOverlay.addEventListener('click', closeSidebar);
    }

    // 2. Dismissible Flash Toasts
    document.querySelectorAll('.toast-close').forEach((btn) => {
      btn.addEventListener('click', () => {
        const toast = btn.closest('.toast');
        if (toast) toast.remove();
      });
    });

    // 3. User Dropdown Menu
    const userMenuToggle = document.getElementById('userMenuToggle');
    const userDropdown = document.getElementById('userDropdown');
    if (userMenuToggle && userDropdown) {
      userMenuToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        userDropdown.classList.toggle('open');
        const notifPanel = document.getElementById('notificationPanel');
        if (notifPanel) notifPanel.classList.remove('open');
      });
    }

    // 4. Notifications Panel
    const notificationsToggle = document.getElementById('notificationsToggle');
    const notificationsNavLink = document.getElementById('notifications-nav-link');
    const notificationPanel = document.getElementById('notificationPanel');
    const notificationList = document.getElementById('notificationList');
    const markAllReadBtn = document.getElementById('markAllRead');

    async function loadNotifications() {
      if (!notificationList) return;
      try {
        const res = await fetch('/api/v1/notifications');
        const json = await res.json();
        if (!json.success || !json.data.length) {
          notificationList.innerHTML = '<div class="empty-state-sm" style="border:none">No notifications yet.</div>';
          return;
        }
        notificationList.innerHTML = json.data
          .map((n) => {
            const href = n.issue_key ? `/issues/${encodeURIComponent(n.issue_key)}` : '#';
            const cls = n.is_read ? 'notification-item' : 'notification-item unread';
            const dateStr = n.created_at ? new Date(n.created_at).toLocaleString() : '';
            return `<a href="${href}" class="${cls}" data-notif-id="${n.id}">
              <div>${escapeHtml(n.message)}</div>
              <small class="text-muted mono">${escapeHtml(dateStr)}</small>
            </a>`;
          })
          .join('');

        notificationList.querySelectorAll('.notification-item.unread').forEach((el) => {
          el.addEventListener('click', () => {
            const id = el.getAttribute('data-notif-id');
            fetch(`/api/v1/notifications/${id}/read`, {
              method: 'POST',
              headers: { 'X-CSRFToken': getCsrfToken() },
            });
          });
        });
      } catch (err) {
        notificationList.innerHTML = '<div class="empty-state-sm" style="border:none">Failed to load notifications.</div>';
      }
    }

    function toggleNotifications(e) {
      e.preventDefault();
      e.stopPropagation();
      if (!notificationPanel) return;
      const isOpen = notificationPanel.classList.toggle('open');
      if (userDropdown) userDropdown.classList.remove('open');
      if (isOpen) loadNotifications();
    }

    if (notificationsToggle) notificationsToggle.addEventListener('click', toggleNotifications);
    if (notificationsNavLink) notificationsNavLink.addEventListener('click', toggleNotifications);

    if (markAllReadBtn) {
      markAllReadBtn.addEventListener('click', async () => {
        await fetch('/api/v1/notifications/read-all', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrfToken() },
        });
        document.querySelectorAll('.notification-badge, .nav-badge').forEach((b) => b.remove());
        loadNotifications();
        window.showToast('All notifications marked as read.', 'success');
      });
    }

    // 5. Global Search
    const searchInput = document.getElementById('globalSearch');
    const searchResults = document.getElementById('searchResults');

    if (searchInput && searchResults) {
      const performSearch = debounce(async (query) => {
        if (query.length < 2) {
          searchResults.classList.remove('open');
          searchResults.innerHTML = '';
          return;
        }
        try {
          const res = await fetch(`/api/v1/search?q=${encodeURIComponent(query)}`);
          const json = await res.json();
          if (!json.success || !json.data.length) {
            searchResults.innerHTML = '<div class="search-result-item text-muted">No matching issues found.</div>';
          } else {
            searchResults.innerHTML = json.data
              .map(
                (i) => `<a href="/issues/${encodeURIComponent(i.issue_key)}" class="search-result-item">
                  <div style="display:flex;justify-content:space-between;align-items:center">
                    <span class="mono" style="color:var(--accent);font-weight:600">${escapeHtml(i.issue_key)}</span>
                    <span class="badge badge-status badge-${escapeHtml(i.status.replace(/_/g, '-'))}">${escapeHtml(i.status.replace(/_/g, ' '))}</span>
                  </div>
                  <div style="font-size:13px">${escapeHtml(i.title)}</div>
                </a>`
              )
              .join('');
          }
          searchResults.classList.add('open');
        } catch (err) {
          searchResults.classList.remove('open');
        }
      }, 220);

      searchInput.addEventListener('input', (e) => performSearch(e.target.value.trim()));
    }

    // 6. Close popovers on outside click / Escape
    document.addEventListener('click', (e) => {
      if (userDropdown && !e.target.closest('.topbar-user-menu')) userDropdown.classList.remove('open');
      if (notificationPanel && !e.target.closest('#notificationsContainer') && !e.target.closest('#notifications-nav-link')) {
        notificationPanel.classList.remove('open');
      }
      if (searchResults && !e.target.closest('.search-wrapper')) searchResults.classList.remove('open');
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        if (searchInput) {
          e.preventDefault();
          searchInput.focus();
        }
      }
      if (e.key === 'Escape') {
        if (userDropdown) userDropdown.classList.remove('open');
        if (notificationPanel) notificationPanel.classList.remove('open');
        if (searchResults) searchResults.classList.remove('open');
        document.querySelectorAll('.modal').forEach((m) => (m.style.display = 'none'));
        closeSidebar();
      }
    });
  });
})();
