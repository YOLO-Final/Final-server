/* ============================================================
   dashboard_charts.js — Canvas 차트 렌더링
   ============================================================ */
'use strict';

/*
 * 이 파일의 역할
 * 1. Chart.js 인스턴스를 만들고, 탭 전환 시 안전하게 제거한다.
 * 2. worker / qa 화면에서 사용하는 공통 차트 렌더 함수를 제공한다.
 * 3. 다크모드 여부에 따라 tooltip / grid / text 색상을 통일한다.
 */

const CHARTS = {
  // canvas id별 Chart.js 인스턴스를 보관한다.
  instances: {},

  // 특정 canvas에 연결된 기존 차트를 제거한다.
  destroy(id) {
    if (this.instances[id]) {
      this.instances[id].destroy();
      delete this.instances[id];
    }
  },

  // 탭 전환 전에 모든 차트를 정리할 때 사용한다.
  destroyAll() {
    Object.keys(this.instances).forEach(id => this.destroy(id));
  },

  // body의 다크 테마 클래스를 기준으로 차트 팔레트를 결정한다.
  isDark() { return document.body.classList.contains('theme-dark'); },

  // tooltip / grid / text에 쓸 공통 색 토큰.
  tokens() {
    return this.isDark()
      ? { text: '#94A3B8', grid: 'rgba(255,255,255,.06)', bg: '#161B27' }
      : { text: '#6B7280', grid: 'rgba(0,0,0,.06)',       bg: '#FFFFFF' };
  },

  inferXAxisKind(labels = []) {
    // x축 라벨 형태를 보고 "시간축"인지 "기간축"인지 자동 추론한다.
    // worker 최근 NG 추세는 HH:MM, 기간 비교/주간 생산량은 날짜 라벨이 들어온다.
    const samples = labels
      .map((v) => String(v ?? '').trim())
      .filter(Boolean)
      .slice(0, 5);
    if (!samples.length) return 'time';

    // HH:MM 형태가 하나라도 있으면 시간축으로 본다.
    if (samples.some((v) => /^\d{1,2}:\d{2}$/.test(v))) {
      return 'time';
    }
    return 'period';
  },

  formatXAxisTitle(value, kind = 'time') {
    // tooltip 제목을 "시간: 14:20" / "기간: 03-21"처럼 통일한다.
    const label = String(value ?? '').trim();
    if (!label) return '';
    return `${kind === 'time' ? '시간' : '기간'}: ${label}`;
  },

  formatXAxisTick(value, kind = 'time') {
    // 실제 데이터 포맷은 여러 형태가 올 수 있으므로
    // 화면에는 사람이 읽기 쉬운 형태로만 축약해서 보여준다.
    const label = String(value ?? '').trim();
    if (!label) return '';

    if (kind === 'time') {
      const hm = label.match(/^(\d{1,2}):(\d{2})$/);
      if (hm) {
        const hh = String(hm[1]).padStart(2, '0');
        return `${hh}:${hm[2]}`;
      }
      return label;
    }

    const ymd = label.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (ymd) return `${ymd[2]}-${ymd[3]}`;

    const md = label.match(/^(\d{1,2})[\/.-](\d{1,2})$/);
    if (md) {
      const mm = String(md[1]).padStart(2, '0');
      const dd = String(md[2]).padStart(2, '0');
      return `${mm}-${dd}`;
    }

    const compact = label.match(/^(\d{2})-(\d{2})$/);
    if (compact) return label;

    return label;
  },

  ensureExternalTooltip(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;
    const host = canvas.parentElement;
    if (!host) return null;

    let tooltip = host.querySelector('.chart-external-tooltip');
    if (tooltip) return tooltip;

    if (window.getComputedStyle(host).position === 'static') {
      host.style.position = 'relative';
    }

    tooltip = document.createElement('div');
    tooltip.className = 'chart-external-tooltip chart-external-tooltip--worker-pie';
    tooltip.setAttribute('aria-hidden', 'true');
    host.appendChild(tooltip);
    return tooltip;
  },

  /* ── Worker / QA / Manager / Promo 차트 렌더 섹션 ── */
  /* ── NG 추세 라인차트 ── */
  /* worker 탭: 최근 NG 건수 + warning/critical 기준선을 함께 그린다. */
  renderNgTrend(canvasId, rows = [], threshold = { warning: 10, critical: 15 }) {
    if (!window.Chart) return;
    this.destroy(canvasId);
    const el = document.getElementById(canvasId);
    if (!el) return;
    const t = this.tokens();
    const labels = rows.map(r => r.time);
    const data   = rows.map(r => r.ng);
    const xKind = this.inferXAxisKind(labels);

    // 최근 시계열 NG + 임계선을 함께 그려서
    // 작업자가 "지금 위험 구간인지"를 한 번에 볼 수 있게 한다.
    const c = new Chart(el.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'NG',
            data,
            borderColor: '#DC2626',
            backgroundColor: 'rgba(220,38,38,.08)',
            fill: true,
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 5,
            pointBackgroundColor: '#DC2626',
            tension: 0.35,
          },
          {
            label: '주의',
            data: labels.map(() => threshold.warning),
            borderColor: '#D97706',
            borderDash: [5, 3],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
          },
          {
            label: '위험',
            data: labels.map(() => threshold.critical),
            borderColor: '#DC2626',
            borderDash: [4, 4],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
          },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: t.bg,
            titleColor: t.text,
            bodyColor: t.text,
            borderColor: '#E2E8F0',
            borderWidth: 1,
            callbacks: {
              title: (items) => this.formatXAxisTitle(items?.[0]?.label, xKind),
              label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y}건`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: t.text,
              font: { size: 10, family: 'IBM Plex Mono' },
              callback: (_value, index) => this.formatXAxisTick(labels[index], xKind),
            },
          },
          y: {
            grid: { color: t.grid },
            ticks: { color: t.text, font: { size: 10, family: 'IBM Plex Mono' } },
          },
        },
      },
    });
    this.instances[canvasId] = c;
  },

  /* ── NG 파이차트 ── */
  /* worker 탭: NG 유형 분포를 doughnut 차트로 보여준다. */
  renderNgPie(canvasId, ngTypes = []) {
    if (!window.Chart) return;
    this.destroy(canvasId);
    const el = document.getElementById(canvasId);
    if (!el) return;
    const t = this.tokens();
    const tooltipEl = this.ensureExternalTooltip(canvasId);

    // 도넛 가운데를 비워서 카드 안 범례/보조 수치와 같이 보이게 한다.
    const c = new Chart(el.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels: ngTypes.map(d => d.name),
        datasets: [{
          data: ngTypes.map(d => d.count),
          backgroundColor: ngTypes.map(d => d.color),
          borderWidth: 2,
          borderColor: t.bg,
          hoverOffset: 6,
        }],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        cutout: '62%',
        plugins: {
          legend: { display: false },
          tooltip: {
            enabled: false,
            external: ({ chart, tooltip }) => {
              if (!tooltipEl) return;

              if (!tooltip || tooltip.opacity === 0 || !tooltip.dataPoints?.length) {
                tooltipEl.style.opacity = '0';
                tooltipEl.style.transform = 'translate3d(0, 0, 0) scale(0.96)';
                return;
              }

              const point = tooltip.dataPoints[0];
              const total = (chart.data.datasets?.[0]?.data || []).reduce((sum, value) => sum + Number(value || 0), 0);
              const count = Number(point.raw || 0);
              const pct = total > 0 ? Math.round((count / total) * 100) : 0;

              tooltipEl.innerHTML = `
                <div class="chart-external-tooltip__title">${point.label}</div>
                <div class="chart-external-tooltip__body">${count}건 · ${pct}%</div>
              `;

              const caretX = tooltip.caretX ?? 0;
              const caretY = tooltip.caretY ?? 0;
              const canvasRect = chart.canvas.getBoundingClientRect();
              const hostRect = chart.canvas.parentElement.getBoundingClientRect();
              const tooltipRect = tooltipEl.getBoundingClientRect();
              const hostWidth = hostRect.width;

              let left = caretX - (tooltipRect.width / 2);
              let top = caretY - tooltipRect.height - 12;

              left = Math.max(8, Math.min(left, hostWidth - tooltipRect.width - 8));
              if (top < 8) {
                top = caretY + 12;
              }

              const offsetX = canvasRect.left - hostRect.left;
              const offsetY = canvasRect.top - hostRect.top;
              tooltipEl.style.left = `${offsetX + left}px`;
              tooltipEl.style.top = `${offsetY + top}px`;
              tooltipEl.style.opacity = '1';
              tooltipEl.style.transform = 'translate3d(0, 0, 0) scale(1)';
            },
          },
        },
      },
    });
    this.instances[canvasId] = c;
  },

  /* ── QA 불량률 바차트 ── */
  /* qa 탭: 원인별 불량 건수를 세로 막대차트로 보여준다. */
  renderQaBar(canvasId, defects = []) {
    if (!window.Chart) return;
    this.destroy(canvasId);
    const el = document.getElementById(canvasId);
    if (!el) return;
    const t = this.tokens();

    // qa 탭에서는 항목별 비교가 중요하므로 세로 막대 형태를 기본으로 쓴다.
    const c = new Chart(el.getContext('2d'), {
      type: 'bar',
      data: {
        labels: defects.map(d => d.class_name),
        datasets: [{
          data: defects.map(d => d.count),
          backgroundColor: defects.map(d => d.color),
          borderRadius: 4,
          borderSkipped: false,
        }],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: t.bg,
            titleColor: t.text,
            bodyColor: t.text,
            borderColor: '#E2E8F0',
            borderWidth: 1,
            callbacks: {
              label: ctx => {
                const total = ctx.dataset.data.reduce((a,b) => a+b, 0);
                const pct = Math.round(ctx.parsed.y / total * 100);
                return `${ctx.parsed.y}건 (${pct}%)`;
              },
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: t.text, font: { size: 10 } } },
          y: { grid: { color: t.grid  }, ticks: { color: t.text, font: { size: 10 } } },
        },
      },
    });
    this.instances[canvasId] = c;
  },

  /* ── QA 추세 스파크라인 ── */
  /* qa 탭: 불량률 추세를 작은 sparkline 형태로 그린다. */
  renderQaSparkline(canvasId, rows = [], threshold = 4.0) {
    if (!window.Chart) return;
    this.destroy(canvasId);
    const el = document.getElementById(canvasId);
    if (!el) return;
    const t = this.tokens();

    // 카드 안 보조 시각화이므로 축/범례를 숨기고 흐름만 빠르게 보여준다.
    const c = new Chart(el.getContext('2d'), {
      type: 'line',
      data: {
        labels: rows.map(r => r.time),
        datasets: [
          {
            data: rows.map(r => r.actual),
            borderColor: '#DC2626',
            backgroundColor: 'rgba(220,38,38,.07)',
            fill: true,
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.3,
          },
          {
            data: rows.map(() => threshold),
            borderColor: '#DC2626',
            borderDash: [4, 3],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
          },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: t.bg,
            titleColor: t.text,
            bodyColor: t.text,
            borderColor: '#E2E8F0',
            borderWidth: 1,
          },
        },
        scales: {
          x: { display: false },
          y: { display: false },
        },
      },
    });
    this.instances[canvasId] = c;
  },

  /* qa 상세 모달: 축/툴팁이 있는 큰 추세 차트 */
  renderQaTrendDetail(canvasId, rows = [], threshold = 4.0) {
    if (!window.Chart) return;
    this.destroy(canvasId);
    const el = document.getElementById(canvasId);
    if (!el) return;
    const t = this.tokens();
    const labels = rows.map(r => r.time);
    const xKind = this.inferXAxisKind(labels);

    // 상세 모달에서는 카드보다 더 많은 맥락이 필요하므로
    // 축/tooltip을 모두 살려서 시간대별 품질 변화를 읽게 한다.
    const c = new Chart(el.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: '불량률',
            data: rows.map(r => r.actual),
            borderColor: '#DC2626',
            backgroundColor: 'rgba(220,38,38,.08)',
            fill: true,
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 5,
            pointBackgroundColor: '#DC2626',
            tension: 0.3,
          },
          {
            label: '임계',
            data: rows.map(() => threshold),
            borderColor: '#DC2626',
            borderDash: [4, 3],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
          },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: t.bg,
            titleColor: t.text,
            bodyColor: t.text,
            borderColor: '#E2E8F0',
            borderWidth: 1,
            callbacks: {
              title: (items) => this.formatXAxisTitle(items?.[0]?.label, xKind),
              label: ctx => {
                const v = Number(ctx.parsed.y);
                return `${ctx.dataset.label}: ${Number.isFinite(v) ? v.toFixed(2) : ctx.parsed.y}%`;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: t.text,
              font: { size: 10, family: 'IBM Plex Mono' },
              callback: (_value, index) => this.formatXAxisTick(labels[index], xKind),
            },
          },
          y: {
            grid: { color: t.grid },
            ticks: {
              color: t.text,
              font: { size: 10, family: 'IBM Plex Mono' },
              callback: value => `${value}%`,
            },
          },
        },
      },
    });
    this.instances[canvasId] = c;
  },

  /* manager 탭: 라인별 OEE 비교 */
  renderManagerOee(canvasId, rows = []) {
    if (!window.Chart) return;
    this.destroy(canvasId);
    const el = document.getElementById(canvasId);
    if (!el) return;
    const t = this.tokens();

    // 관리자 탭은 라인 간 상대 비교가 중요하므로
    // 실적/목표를 같은 축에서 나란히 비교하게 한다.
    const c = new Chart(el.getContext('2d'), {
      type: 'bar',
      data: {
        labels: rows.map(r => r.line),
        datasets: [
          {
            label: '실적',
            data: rows.map(r => r.actual),
            backgroundColor: rows.map(r => r.actual >= 85 ? '#10B981' : r.actual >= 70 ? '#F59E0B' : '#EF4444'),
            borderRadius: 6,
            borderSkipped: false,
          },
          {
            label: '목표',
            data: rows.map(r => r.target),
            backgroundColor: 'rgba(91,124,246,.18)',
            borderColor: '#5B7CF6',
            borderWidth: 1,
            borderRadius: 6,
            borderSkipped: false,
          },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: { color: t.text, font: { size: 10 } },
          },
          tooltip: {
            backgroundColor: t.bg,
            titleColor: t.text,
            bodyColor: t.text,
            borderColor: '#E2E8F0',
            borderWidth: 1,
            callbacks: {
              label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y}%`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: t.text,
              font: { size: 10 },
              callback: (_value, index) => this.formatXAxisTick(labels[index], xKind),
            },
          },
          y: {
            grid: { color: t.grid },
            ticks: { color: t.text, font: { size: 10, family: 'IBM Plex Mono' }, callback: v => `${v}%` },
          },
        },
      },
    });
    this.instances[canvasId] = c;
  },

  /* manager 탭: 시간대별 생산량 */
  renderManagerProduction(canvasId, rows = []) {
    if (!window.Chart) return;
    this.destroy(canvasId);
    const el = document.getElementById(canvasId);
    if (!el) return;
    const t = this.tokens();
    const labels = rows.map(r => r.time);
    const xKind = this.inferXAxisKind(labels);

    // 관리자 생산 추세는 "실적 vs 계획" 차이를 읽는 것이 목적이라
    // 두 개의 선을 같은 시계열 위에 겹쳐서 그린다.
    const c = new Chart(el.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: '실적',
            data: rows.map(r => r.actual),
            borderColor: '#5B7CF6',
            backgroundColor: 'rgba(91,124,246,.08)',
            fill: true,
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 5,
            tension: 0.3,
          },
          {
            label: '계획',
            data: rows.map(r => r.plan),
            borderColor: '#64748B',
            borderDash: [5, 3],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
            tension: 0.3,
          },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: { color: t.text, font: { size: 10 } },
          },
          tooltip: {
            backgroundColor: t.bg,
            titleColor: t.text,
            bodyColor: t.text,
            borderColor: '#E2E8F0',
            borderWidth: 1,
            callbacks: {
              title: (items) => this.formatXAxisTitle(items?.[0]?.label, xKind),
              label: ctx => `${ctx.dataset.label}: ${Number(ctx.parsed.y).toLocaleString()} pcs`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: t.text,
              font: { size: 10 },
              callback: (_value, index) => this.formatXAxisTick(labels[index], xKind),
            },
          },
          y: {
            grid: { color: t.grid },
            ticks: {
              color: t.text,
              font: { size: 10, family: 'IBM Plex Mono' },
              callback: v => `${Math.round(Number(v) / 1000)}k`,
            },
          },
        },
      },
    });
    this.instances[canvasId] = c;
  },

  /* manager 탭: 전체 불량률 추세 */
  renderManagerDefectTrend(canvasId, rows = [], threshold = 4.0) {
    if (!window.Chart) return;
    this.destroy(canvasId);
    const el = document.getElementById(canvasId);
    if (!el) return;
    const t = this.tokens();
    const labels = rows.map(r => r.time);
    const xKind = this.inferXAxisKind(labels);

    // 관리자용 불량률 추세는 위험 구간을 빠르게 찾는 게 목적이라
    // 임계선과 포인트 강조색을 같이 사용한다.
    const c = new Chart(el.getContext('2d'), {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: '불량률',
            data: rows.map(r => r.rate),
            borderColor: '#EF4444',
            backgroundColor: 'rgba(239,68,68,.08)',
            fill: true,
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 5,
            pointBackgroundColor: rows.map(r => r.rate >= threshold ? '#EF4444' : '#10B981'),
            tension: 0.3,
          },
          {
            label: '임계',
            data: rows.map(() => threshold),
            borderColor: '#EF4444',
            borderDash: [4, 3],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
          },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: t.bg,
            titleColor: t.text,
            bodyColor: t.text,
            borderColor: '#E2E8F0',
            borderWidth: 1,
            callbacks: {
              title: (items) => this.formatXAxisTitle(items?.[0]?.label, xKind),
              label: ctx => ctx.dataset.label === '불량률'
                ? `불량률: ${Number(ctx.parsed.y).toFixed(1)}%`
                : `임계: ${threshold.toFixed(1)}%`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              color: t.text,
              font: { size: 10 },
              callback: (_value, index) => this.formatXAxisTick(labels[index], xKind),
            },
          },
          y: {
            grid: { color: t.grid },
            ticks: {
              color: t.text,
              font: { size: 10, family: 'IBM Plex Mono' },
              callback: v => `${v}%`,
            },
          },
        },
      },
    });
    this.instances[canvasId] = c;
  },

  /* promo 탭: 주간 생산량 bar + 목표선 */
  renderPromoWeekChart(canvasId, rows = []) {
    if (!window.Chart) return;
    this.destroy(canvasId);
    const el = document.getElementById(canvasId);
    if (!el) return;
    const t = this.tokens();
    const labels = rows.map(r => r.day);
    const xKind = this.inferXAxisKind(labels);

    const c = new Chart(el.getContext('2d'), {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: '실적',
            data: rows.map(r => r.actual),
            backgroundColor: rows.map((_, idx) => idx === rows.length - 1 ? 'rgba(74,124,255,.48)' : 'rgba(74,124,255,.25)'),
            borderColor: rows.map((_, idx) => idx === rows.length - 1 ? '#4A7CFF' : 'rgba(74,124,255,.5)'),
            borderWidth: 1,
            borderRadius: 4,
            borderSkipped: false,
          },
          {
            label: '목표',
            type: 'line',
            data: rows.map(r => r.target),
            borderColor: 'rgba(90,112,144,.6)',
            borderDash: [5, 4],
            borderWidth: 1.5,
            pointRadius: 0,
            fill: false,
            tension: 0.2,
          },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: t.bg,
            titleColor: t.text,
            bodyColor: t.text,
            borderColor: '#E2E8F0',
            borderWidth: 1,
            callbacks: {
              title: (items) => this.formatXAxisTitle(items?.[0]?.label, xKind),
              label: ctx => `${ctx.dataset.label}: ${Number(ctx.parsed.y).toLocaleString()}pcs`,
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: t.text, font: { size: 10 } } },
          y: {
            grid: { color: t.grid },
            ticks: {
              color: t.text,
              font: { size: 10, family: 'IBM Plex Mono' },
              callback: v => `${Math.round(Number(v) / 1000)}k`,
            },
            suggestedMin: 8000,
            suggestedMax: 14000,
          },
        },
      },
    });
    this.instances[canvasId] = c;
  },

  /* promo 탭: 라인별 가동량 (배너 크기에 유동 대응하도록 취급) */
  renderPromoLineStatus(canvasId, rows = []) {
    if (!window.Chart) return;
    this.destroy(canvasId);
    const el = document.getElementById(canvasId);
    if (!el) return;

    const labels = rows.map(r => r.line);
    const actual = rows.map(r => Number(r.output) || 0);
    const oee = rows.map(r => Number(r.oee) || 0);
    const t = this.tokens();

    const c = new Chart(el.getContext('2d'), {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: '생산량',
            data: actual,
            backgroundColor: rows.map((_, idx) => idx === rows.length - 1 ? 'rgba(74,124,255,.48)' : 'rgba(74,124,255,.25)'),
            borderColor: 'rgba(74,124,255,.6)',
            borderWidth: 1,
            borderRadius: 4,
            borderSkipped: false,
          },
          {
            label: 'OEE',
            type: 'line',
            data: oee,
            yAxisID: 'oee',
            borderColor: 'rgba(16,185,129,.8)',
            borderWidth: 2,
            pointRadius: 3,
            tension: 0.25,
            fill: false,
          },
        ],
      },
      options: {
        animation: false,
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'nearest', intersect: false },
        plugins: {
          legend: { display: true, position: 'top' },
          tooltip: {
            backgroundColor: t.bg,
            titleColor: t.text,
            bodyColor: t.text,
            borderColor: '#E2E8F0',
            borderWidth: 1,
            callbacks: {
              title: (items) => `라인: ${items?.[0]?.label ?? ''}`,
              label: (ctx) => ctx.dataset.type === 'line'
                ? `OEE: ${Number(ctx.parsed.y).toFixed(1)}%`
                : `생산량: ${Number(ctx.parsed.y).toLocaleString()} pcs`,
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: t.text, font: { size: 10 } } },
          y: {
            grid: { color: t.grid },
            ticks: { color: t.text, font: { size: 10, family: 'IBM Plex Mono' } },
            title: { display: true, text: '생산량', color: t.text },
          },
          oee: {
            position: 'right',
            grid: { display: false },
            ticks: {
              color: t.text,
              font: { size: 10, family: 'IBM Plex Mono' },
              callback: v => `${v}%`,
            },
            title: { display: true, text: 'OEE', color: t.text },
            min: 0,
            max: 100,
          },
        },
      },
    });

    this.instances[canvasId] = c;
  },
};
