/**
 * IntelliTrack Analytics & Dashboard Charts
 * Renders real database metrics via Chart.js using the Swiss Grid industrial palette.
 */

(function () {
  'use strict';

  const PALETTE = {
    open: '#476D8A',
    progress: '#B67B25',
    resolved: '#48745A',
    closed: '#74766F',
    critical: '#B33A32',
    accent: '#E76F32',
    ink: '#22231F',
    muted: '#6F7068',
    line: '#D3CFC4',
  };

  function getProjectQuery() {
    const grid = document.querySelector('.charts-grid');
    const pid = grid ? grid.getAttribute('data-project-id') : '';
    return pid ? `?project_id=${encodeURIComponent(pid)}` : '';
  }

  async function fetchChartData(type) {
    const res = await fetch(`/api/v1/analytics/charts/${type}${getProjectQuery()}`);
    const json = await res.json();
    return json.success ? json.data : { labels: [], values: [] };
  }

  function renderEmptyChart(canvas, message) {
    const parent = canvas.parentElement;
    if (parent) {
      parent.innerHTML = `<div class="empty-state-sm" style="border:none;padding-top:90px">${message}</div>`;
    }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    if (typeof Chart === 'undefined') return;

    Chart.defaults.font.family = '"Inter", "Helvetica Neue", Arial, sans-serif';
    Chart.defaults.color = PALETTE.muted;

    // 1. Status Doughnut Chart
    const statusCanvas = document.getElementById('statusChart');
    if (statusCanvas) {
      const data = await fetchChartData('status');
      if (!data.labels.length) {
        renderEmptyChart(statusCanvas, 'No status data recorded.');
      } else {
        new Chart(statusCanvas, {
          type: 'doughnut',
          data: {
            labels: data.labels,
            datasets: [
              {
                data: data.values,
                backgroundColor: [
                  PALETTE.open,
                  PALETTE.progress,
                  PALETTE.accent,
                  PALETTE.resolved,
                  PALETTE.closed,
                  PALETTE.critical,
                  '#5C6F7B',
                ],
                borderColor: '#FBFAF6',
                borderWidth: 2,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'right', labels: { boxWidth: 12 } } },
          },
        });
      }
    }

    // 2. Severity Bar Chart
    const severityCanvas = document.getElementById('severityChart');
    if (severityCanvas) {
      const data = await fetchChartData('severity');
      if (!data.labels.length) {
        renderEmptyChart(severityCanvas, 'No severity data recorded.');
      } else {
        const colors = data.labels.map((lbl) => {
          const l = lbl.toLowerCase();
          if (l === 'critical') return PALETTE.critical;
          if (l === 'major') return PALETTE.accent;
          if (l === 'minor') return PALETTE.open;
          return PALETTE.closed;
        });
        new Chart(severityCanvas, {
          type: 'bar',
          data: {
            labels: data.labels,
            datasets: [{ label: 'Issues', data: data.values, backgroundColor: colors, borderRadius: 3 }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
              y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: PALETTE.line } },
              x: { grid: { display: false } },
            },
          },
        });
      }
    }

    // 3. Category Horizontal Bar Chart
    const categoryCanvas = document.getElementById('categoryChart');
    if (categoryCanvas) {
      const data = await fetchChartData('category');
      if (!data.labels.length) {
        renderEmptyChart(categoryCanvas, 'No category data recorded.');
      } else {
        new Chart(categoryCanvas, {
          type: 'bar',
          data: {
            labels: data.labels,
            datasets: [{ label: 'Defects', data: data.values, backgroundColor: PALETTE.open, borderRadius: 3 }],
          },
          options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
              x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: PALETTE.line } },
              y: { grid: { display: false } },
            },
          },
        });
      }
    }

    // 4. Defects Over Time Line Chart
    const timelineCanvas = document.getElementById('timelineChart');
    if (timelineCanvas) {
      const data = await fetchChartData('timeline');
      if (!data.labels.length) {
        renderEmptyChart(timelineCanvas, 'No timeline data recorded.');
      } else {
        new Chart(timelineCanvas, {
          type: 'line',
          data: {
            labels: data.labels.map((d) => d.slice(5)),
            datasets: [
              {
                label: 'Reported Issues',
                data: data.values,
                borderColor: PALETTE.accent,
                backgroundColor: 'rgba(231, 111, 50, 0.12)',
                fill: true,
                tension: 0.2,
                pointRadius: 2,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
              y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: PALETTE.line } },
              x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } },
            },
          },
        });
      }
    }
  });
})();
