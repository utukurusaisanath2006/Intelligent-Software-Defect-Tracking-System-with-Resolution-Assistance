/**
 * IntelliTrack Analytics & Dashboard Charts
 * Zero-dependency, offline-first enterprise charting engine with Deep Midnight Teal (#0B3048),
 * Soft Pearl (#F2F0E9), and Neon Lime (#B9F12F) palette.
 * Automatically polyfills window.Chart if external CDN is blocked or unavailable.
 */

(function () {
  'use strict';

  const PALETTE = {
    teal: '#0B3048',
    tealDark: '#072132',
    tealLight: '#134464',
    paper: '#F2F0E9',
    lime: '#B9F12F',
    ink: '#0B3048',
    muted: '#4D6777',
    line: '#D8D4C7',
    lineSoft: '#E5E2D8',
    surface: '#FFFFFF',
    // Status colors
    statusOpen: '#0B3048',
    statusProgress: '#84B314',
    statusResolved: '#18683B',
    statusClosed: '#5A6A74',
    statusCritical: '#B3261E',
    statusMajor: '#DDA13B',
    statusMinor: '#0B3048',
  };

  /**
   * Helper to draw rounded rectangles on HTML5 canvas with cross-browser compatibility
   */
  function drawRoundRect(ctx, x, y, w, h, r) {
    if (w <= 0 || h <= 0) return;
    if (typeof ctx.roundRect === 'function') {
      ctx.roundRect(x, y, w, h, r);
    } else {
      const radius = typeof r === 'number' ? r : (Array.isArray(r) ? r[0] : 0);
      ctx.moveTo(x + radius, y);
      ctx.lineTo(x + w - radius, y);
      ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
      ctx.lineTo(x + w, y + h - radius);
      ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
      ctx.lineTo(x + radius, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
      ctx.lineTo(x, y + radius);
      ctx.quadraticCurveTo(x, y, x + radius, y);
    }
  }

  /**
   * Built-in native high-definition Canvas Chart Engine
   */
  class IntelliChart {
    constructor(canvas, config) {
      if (typeof canvas === 'string') {
        canvas = document.getElementById(canvas);
      }
      if (!canvas) return;

      this.canvas = canvas;
      this.config = config || {};
      this.type = this.config.type || 'bar';
      this.data = this.config.data || { labels: [], datasets: [] };
      this.options = this.config.options || {};
      this.ctx = canvas.getContext('2d');

      this._resizeHandler = this._handleResize.bind(this);
      window.addEventListener('resize', this._resizeHandler);

      this.render();
    }

    _handleResize() {
      clearTimeout(this._resizeTimer);
      this._resizeTimer = setTimeout(() => {
        this.render();
      }, 150);
    }

    destroy() {
      window.removeEventListener('resize', this._resizeHandler);
      if (this.ctx && this.canvas) {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      }
    }

    render() {
      if (!this.canvas || !this.ctx) return;

      const parent = this.canvas.parentElement;
      const width = parent ? parent.clientWidth : (this.canvas.width || 400);
      const height = parent ? (parent.clientHeight || 260) : 260;

      if (width <= 0 || height <= 0) return;

      const dpr = window.devicePixelRatio || 1;
      this.canvas.width = Math.floor(width * dpr);
      this.canvas.height = Math.floor(height * dpr);
      this.canvas.style.width = width + 'px';
      this.canvas.style.height = height + 'px';

      this.ctx.save();
      this.ctx.scale(dpr, dpr);
      this.ctx.clearRect(0, 0, width, height);

      const dataset = (this.data.datasets && this.data.datasets[0]) || { data: [] };
      const labels = this.data.labels || [];
      const values = dataset.data || [];

      if (!labels.length || !values.length) {
        this._renderEmpty(width, height, 'No chart data available');
        this.ctx.restore();
        return;
      }

      if (this.type === 'doughnut') {
        this._renderDoughnut(width, height, labels, values, dataset.backgroundColor);
      } else if (this.type === 'line') {
        this._renderLine(width, height, labels, values);
      } else if (this.type === 'bar') {
        if (this.options && this.options.indexAxis === 'y') {
          this._renderHorizontalBar(width, height, labels, values);
        } else {
          this._renderVerticalBar(width, height, labels, values, dataset.backgroundColor);
        }
      }

      this.ctx.restore();
    }

    _renderEmpty(width, height, message) {
      const ctx = this.ctx;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.font = '500 13px "Inter", "Helvetica Neue", sans-serif';
      ctx.fillStyle = PALETTE.muted;
      ctx.fillText(message, width / 2, height / 2);
    }

    _renderDoughnut(w, h, labels, values, colors) {
      const ctx = this.ctx;
      const total = values.reduce((sum, v) => sum + (Number(v) || 0), 0);
      if (total <= 0) {
        this._renderEmpty(w, h, 'No recorded issues');
        return;
      }

      const defaultColors = [
        PALETTE.teal,
        PALETTE.statusProgress,
        PALETTE.lime,
        PALETTE.statusResolved,
        PALETTE.statusClosed,
        PALETTE.statusCritical,
        PALETTE.tealLight,
        PALETTE.statusMajor,
      ];
      const paletteList = Array.isArray(colors) && colors.length ? colors : defaultColors;

      const isNarrow = w < 440;
      const cx = isNarrow ? w / 2 : Math.max(75, Math.min(w * 0.32, 130));
      const cy = isNarrow ? h * 0.42 : h / 2;
      const outerR = Math.max(30, Math.min(cx - 15, cy - 15, 95));
      const innerR = outerR * 0.62;

      let currentAngle = -0.5 * Math.PI;

      // Draw Arcs
      for (let i = 0; i < values.length; i++) {
        const val = Number(values[i]) || 0;
        if (val <= 0) continue;
        const sliceAngle = (val / total) * (2 * Math.PI);
        const endAngle = currentAngle + sliceAngle;

        ctx.beginPath();
        ctx.arc(cx, cy, outerR, currentAngle, endAngle);
        ctx.arc(cx, cy, innerR, endAngle, currentAngle, true);
        ctx.closePath();

        ctx.fillStyle = paletteList[i % paletteList.length];
        ctx.fill();

        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 2;
        ctx.stroke();

        currentAngle = endAngle;
      }

      // Center Stat
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.font = '700 24px "Inter", "Helvetica Neue", sans-serif';
      ctx.fillStyle = PALETTE.teal;
      ctx.fillText(total, cx, cy - 9);

      ctx.font = '600 10px "Inter", "Helvetica Neue", sans-serif';
      ctx.fillStyle = PALETTE.muted;
      ctx.fillText('TOTAL', cx, cy + 12);

      // Legend on the Right
      if (!isNarrow) {
        const legendX = cx + outerR + 24;
        const itemH = Math.min(22, (h - 20) / labels.length);
        const startY = (h - labels.length * itemH) / 2;

        ctx.textBaseline = 'middle';
        for (let i = 0; i < labels.length; i++) {
          const y = startY + i * itemH + itemH / 2;
          const val = Number(values[i]) || 0;
          const pct = Math.round((val / total) * 100);

          // Swatch
          ctx.beginPath();
          ctx.fillStyle = paletteList[i % paletteList.length];
          drawRoundRect(ctx, legendX, y - 5, 10, 10, 2);
          ctx.fill();

          // Label
          ctx.font = '500 11px "Inter", "Helvetica Neue", sans-serif';
          ctx.fillStyle = PALETTE.teal;
          ctx.textAlign = 'left';
          ctx.fillText(labels[i], legendX + 16, y);

          // Value & %
          ctx.font = '600 11px "Inter", "Helvetica Neue", sans-serif';
          ctx.fillStyle = PALETTE.muted;
          ctx.textAlign = 'right';
          ctx.fillText(`${val} (${pct}%)`, w - 10, y);
        }
      }
    }

    _renderVerticalBar(w, h, labels, values, colors) {
      const ctx = this.ctx;
      const padTop = 26;
      const padBottom = 34;
      const padLeft = 36;
      const padRight = 16;
      const cw = w - padLeft - padRight;
      const ch = h - padTop - padBottom;

      const numValues = values.map((v) => Number(v) || 0);
      const maxVal = Math.max(...numValues, 1);
      const niceMax = Math.ceil(maxVal * 1.25) || 5;

      // Grid Lines
      const steps = 4;
      ctx.strokeStyle = PALETTE.lineSoft;
      ctx.lineWidth = 1;
      for (let s = 0; s <= steps; s++) {
        const gy = padTop + ch - (s / steps) * ch;
        ctx.beginPath();
        ctx.moveTo(padLeft, gy);
        ctx.lineTo(padLeft + cw, gy);
        ctx.stroke();

        ctx.font = '10px "Inter", "Helvetica Neue", sans-serif';
        ctx.fillStyle = PALETTE.muted;
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.fillText(Math.round((s / steps) * niceMax), padLeft - 6, gy);
      }

      // Vertical Bars
      const slotW = cw / labels.length;
      const barW = Math.min(48, Math.max(20, slotW * 0.52));

      for (let i = 0; i < labels.length; i++) {
        const val = numValues[i];
        const barH = (val / niceMax) * ch;
        const bx = padLeft + i * slotW + (slotW - barW) / 2;
        const by = padTop + ch - barH;

        let barColor = PALETTE.teal;
        if (Array.isArray(colors) && colors[i]) {
          barColor = colors[i];
        }

        ctx.beginPath();
        ctx.fillStyle = barColor;
        drawRoundRect(ctx, bx, by, barW, barH, [4, 4, 0, 0]);
        ctx.fill();

        // Count Value on Top
        ctx.font = '600 11px "Inter", "Helvetica Neue", sans-serif';
        ctx.fillStyle = PALETTE.teal;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        ctx.fillText(val, bx + barW / 2, by - 4);

        // Label on Bottom
        ctx.font = '500 11px "Inter", "Helvetica Neue", sans-serif';
        ctx.fillStyle = PALETTE.muted;
        ctx.textBaseline = 'top';
        ctx.fillText(labels[i], bx + barW / 2, padTop + ch + 8);
      }
    }

    _renderHorizontalBar(w, h, labels, values) {
      const ctx = this.ctx;
      const padTop = 14;
      const padBottom = 14;
      const padLeft = 110;
      const padRight = 44;
      const cw = w - padLeft - padRight;
      const ch = h - padTop - padBottom;

      const numValues = values.map((v) => Number(v) || 0);
      const maxVal = Math.max(...numValues, 1);
      const rowH = ch / labels.length;
      const barH = Math.min(12, Math.max(8, rowH * 0.52));

      for (let i = 0; i < labels.length; i++) {
        const cy = padTop + i * rowH + rowH / 2;
        const by = cy - barH / 2;
        const val = numValues[i];

        // Category Label
        ctx.font = '500 11px "Inter", "Helvetica Neue", sans-serif';
        ctx.fillStyle = PALETTE.teal;
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.fillText(labels[i], padLeft - 10, cy);

        // Background Track
        ctx.beginPath();
        ctx.fillStyle = PALETTE.lineSoft;
        drawRoundRect(ctx, padLeft, by, cw, barH, 3);
        ctx.fill();

        // Progress Bar
        const barW = Math.max(4, (val / maxVal) * cw);
        ctx.beginPath();
        ctx.fillStyle = PALETTE.teal;
        drawRoundRect(ctx, padLeft, by, barW, barH, 3);
        ctx.fill();

        // Count Badge
        ctx.font = '600 11px "Inter", "Helvetica Neue", sans-serif';
        ctx.fillStyle = PALETTE.muted;
        ctx.textAlign = 'left';
        ctx.fillText(val, padLeft + barW + 8, cy);
      }
    }

    _renderLine(w, h, labels, values) {
      const ctx = this.ctx;
      const padTop = 20;
      const padBottom = 30;
      const padLeft = 32;
      const padRight = 16;
      const cw = w - padLeft - padRight;
      const ch = h - padTop - padBottom;

      const numValues = values.map((v) => Number(v) || 0);
      const maxVal = Math.max(...numValues, 1);
      const niceMax = Math.ceil(maxVal * 1.3) || 4;

      // Horizontal Grid Lines
      const steps = 4;
      ctx.strokeStyle = PALETTE.lineSoft;
      ctx.lineWidth = 1;
      for (let s = 0; s <= steps; s++) {
        const gy = padTop + ch - (s / steps) * ch;
        ctx.beginPath();
        ctx.moveTo(padLeft, gy);
        ctx.lineTo(padLeft + cw, gy);
        ctx.stroke();

        ctx.font = '10px "Inter", "Helvetica Neue", sans-serif';
        ctx.fillStyle = PALETTE.muted;
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        ctx.fillText(Math.round((s / steps) * niceMax), padLeft - 6, gy);
      }

      // Compute Points
      const n = values.length;
      const points = [];
      for (let i = 0; i < n; i++) {
        const px = padLeft + (i / Math.max(1, n - 1)) * cw;
        const py = padTop + ch - (numValues[i] / niceMax) * ch;
        points.push({ x: px, y: py, val: numValues[i], label: labels[i] });
      }

      if (!points.length) return;

      // Area Fill
      const grad = ctx.createLinearGradient(0, padTop, 0, padTop + ch);
      grad.addColorStop(0, 'rgba(11, 48, 72, 0.18)');
      grad.addColorStop(1, 'rgba(11, 48, 72, 0.01)');

      ctx.beginPath();
      ctx.moveTo(points[0].x, padTop + ch);
      for (let i = 0; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
      }
      ctx.lineTo(points[points.length - 1].x, padTop + ch);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();

      // Stroke Line
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
      }
      ctx.strokeStyle = PALETTE.teal;
      ctx.lineWidth = 2.5;
      ctx.stroke();

      // Data Points
      for (let i = 0; i < points.length; i++) {
        const pt = points[i];
        if (pt.val > 0) {
          ctx.beginPath();
          ctx.arc(pt.x, pt.y, 4.5, 0, Math.PI * 2);
          ctx.fillStyle = PALETTE.teal;
          ctx.fill();

          ctx.beginPath();
          ctx.arc(pt.x, pt.y, 2.5, 0, Math.PI * 2);
          ctx.fillStyle = PALETTE.lime;
          ctx.fill();

          ctx.font = '600 10px "Inter", "Helvetica Neue", sans-serif';
          ctx.fillStyle = PALETTE.teal;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'bottom';
          ctx.fillText(pt.val, pt.x, pt.y - 6);
        }
      }

      // X Axis Date Labels (every ~5 intervals)
      const step = Math.max(1, Math.floor(n / 5));
      ctx.font = '10px "Inter", "Helvetica Neue", sans-serif';
      ctx.fillStyle = PALETTE.muted;
      ctx.textBaseline = 'top';
      for (let i = 0; i < n; i += step) {
        const pt = points[i];
        ctx.textAlign = i === 0 ? 'left' : (i + step >= n ? 'right' : 'center');
        ctx.fillText(pt.label, pt.x, padTop + ch + 8);
      }
    }
  }

  // Register IntelliChart globally as a seamless offline polyfill
  window.IntelliChart = IntelliChart;
  if (typeof window.Chart === 'undefined') {
    window.Chart = IntelliChart;
  }

  function getProjectQuery() {
    const grid = document.querySelector('.charts-grid');
    const pid = grid ? grid.getAttribute('data-project-id') : '';
    return pid ? `?project_id=${encodeURIComponent(pid)}` : '';
  }

  async function fetchChartData(type) {
    try {
      const res = await fetch(`/api/v1/analytics/charts/${type}${getProjectQuery()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      return json.success ? json.data : { labels: [], values: [] };
    } catch (err) {
      console.warn(`Analytics fetch failed for ${type}:`, err);
      return { labels: [], values: [] };
    }
  }

  function renderEmptyChart(canvas, message) {
    const parent = canvas ? canvas.parentElement : null;
    if (parent) {
      parent.innerHTML = `<div class="empty-state-sm" style="border:none;padding-top:90px">${message}</div>`;
    }
  }

  function instantiateChart(canvas, config) {
    try {
      if (typeof window.Chart !== 'undefined') {
        return new window.Chart(canvas, config);
      }
    } catch (e) {
      console.warn('Primary chart instantiation failed, falling back to IntelliChart:', e);
    }
    return new IntelliChart(canvas, config);
  }

  async function initAnalyticsCharts() {
    // 1. Status Doughnut Chart
    const statusCanvas = document.getElementById('statusChart');
    if (statusCanvas) {
      const data = await fetchChartData('status');
      if (!data.labels || !data.labels.length) {
        renderEmptyChart(statusCanvas, 'No status data recorded.');
      } else {
        instantiateChart(statusCanvas, {
          type: 'doughnut',
          data: {
            labels: data.labels,
            datasets: [
              {
                data: data.values,
                backgroundColor: [
                  PALETTE.statusOpen,
                  PALETTE.statusProgress,
                  PALETTE.lime,
                  PALETTE.statusResolved,
                  PALETTE.statusClosed,
                  PALETTE.statusCritical,
                  PALETTE.tealLight,
                  PALETTE.statusMajor,
                ],
                borderColor: '#FFFFFF',
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
      if (!data.labels || !data.labels.length) {
        renderEmptyChart(severityCanvas, 'No severity data recorded.');
      } else {
        const colors = data.labels.map((lbl) => {
          const l = lbl.toLowerCase();
          if (l === 'critical') return PALETTE.statusCritical;
          if (l === 'major') return PALETTE.statusMajor;
          if (l === 'minor') return PALETTE.teal;
          return PALETTE.statusClosed;
        });

        instantiateChart(severityCanvas, {
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
      if (!data.labels || !data.labels.length) {
        renderEmptyChart(categoryCanvas, 'No category data recorded.');
      } else {
        instantiateChart(categoryCanvas, {
          type: 'bar',
          data: {
            labels: data.labels,
            datasets: [{ label: 'Defects', data: data.values, backgroundColor: PALETTE.teal, borderRadius: 3 }],
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
      if (!data.labels || !data.labels.length) {
        renderEmptyChart(timelineCanvas, 'No timeline data recorded.');
      } else {
        instantiateChart(timelineCanvas, {
          type: 'line',
          data: {
            labels: data.labels.map((d) => d.slice(5)),
            datasets: [
              {
                label: 'Reported Issues',
                data: data.values,
                borderColor: PALETTE.teal,
                backgroundColor: 'rgba(11, 48, 72, 0.08)',
                pointBackgroundColor: PALETTE.lime,
                pointBorderColor: PALETTE.teal,
                fill: true,
                tension: 0.2,
                pointRadius: 3,
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
  }

  // Ensure execution regardless of script load timing
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAnalyticsCharts);
  } else {
    initAnalyticsCharts();
  }
})();
