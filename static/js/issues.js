/**
 * IntelliTrack Issue Form & Detail Interactions
 * Handles explainable classification suggestions on issue creation.
 */

(function () {
  'use strict';

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  document.addEventListener('DOMContentLoaded', () => {
    const suggestBtn = document.getElementById('getSuggestionsBtn');
    const panel = document.getElementById('suggestionsPanel');

    if (suggestBtn && panel) {
      suggestBtn.addEventListener('click', async () => {
        const title = (document.getElementById('title')?.value || '').trim();
        const description = (document.getElementById('description')?.value || '').trim();
        const component = (document.getElementById('component')?.value || '').trim();
        const issueType = document.getElementById('issue_type')?.value || 'bug';

        if (!title && !description) {
          if (window.showToast) window.showToast('Enter a title or description first for classification suggestions.', 'info');
          return;
        }

        suggestBtn.disabled = true;
        suggestBtn.textContent = 'Analyzing...';

        try {
          const res = await fetch('/api/v1/classify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title,
              description,
              component,
              issue_type: issueType,
            }),
          });
          const json = await res.json();
          if (!json.success) {
            throw new Error(json.error || 'Classification failed');
          }

          const d = json.data;
          panel.innerHTML = `
            <div style="font-weight:600;margin-bottom:6px;text-transform:uppercase;color:var(--ink-muted)">Suggested Classification</div>
            <div style="margin-bottom:6px">
              <strong>Category:</strong> ${escapeHtml(d.suggested_category.replace(/_/g, ' '))} (${Math.round(d.category_confidence)}%)<br>
              <span class="text-muted">${escapeHtml(d.category_reason)}</span>
            </div>
            <div style="margin-bottom:6px">
              <strong>Severity:</strong> ${escapeHtml(d.suggested_severity)}<br>
              <span class="text-muted">${escapeHtml(d.severity_reason)}</span>
            </div>
            <div style="margin-bottom:10px">
              <strong>Priority:</strong> ${escapeHtml(d.suggested_priority)}<br>
              <span class="text-muted">${escapeHtml(d.priority_reason)}</span>
            </div>
            <div style="display:flex;gap:6px">
              <button type="button" class="btn btn-primary btn-sm" id="acceptSuggestionsBtn">Apply Suggestions</button>
              <button type="button" class="btn btn-secondary btn-sm" id="dismissSuggestionsBtn">Dismiss</button>
            </div>
          `;
          panel.style.display = 'block';

          document.getElementById('acceptSuggestionsBtn').addEventListener('click', () => {
            const catSelect = document.getElementById('category');
            const sevSelect = document.getElementById('severity');
            const priSelect = document.getElementById('priority');
            if (catSelect) catSelect.value = d.suggested_category;
            if (sevSelect) sevSelect.value = d.suggested_severity;
            if (priSelect) priSelect.value = d.suggested_priority;
            panel.style.display = 'none';
            if (window.showToast) window.showToast('Classification suggestions applied.', 'success');
          });

          document.getElementById('dismissSuggestionsBtn').addEventListener('click', () => {
            panel.style.display = 'none';
          });
        } catch (err) {
          if (window.showToast) window.showToast('Unable to fetch classification suggestions.', 'error');
        } finally {
          suggestBtn.disabled = false;
          suggestBtn.textContent = 'Suggest Classification';
        }
      });
    }
  });
})();
