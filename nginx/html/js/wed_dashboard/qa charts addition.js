/*
 * wed_dashboard QA 전용 보강 차트 파일.
 * 기본 공통 차트와 별도로, QA 탭의 불량률 추세를 Canvas 기반 인터랙션
 * (hover, threshold 강조, 애니메이션)으로 그리는 추가 렌더러를 담고 있다.
 */
/* ============================================================
   QA 탭 전용 Canvas 기반 추세 차트
   renderQaDefectSparklineMini 는 유지하고, 아래 함수를 추가로 정의.
   qaLayout 에서는 renderQaDefectTrendCanvas 를 호출.
   ============================================================ */

// QA 추세 차트 상태 관리
const QA_TREND_STATE = {
  raf: null,
  hoverIdx: -1,
  animT: 0,
};
const QA_PL = 40, QA_PR = 68, QA_PT = 14, QA_PB = 24;

/**
 * renderQaDefectTrendCanvas
 * Canvas 기반 불량률 추세 차트.
 * - 마우스 hover → 세로 커서선 + 툴팁 (getBoundingClientRect CSS 좌표 기준)
 * - 임계선 (qa_defect_rate criticalValue) 빨간 점선
 * - 임계 초과 구간 빨간 라인 + 영역
 * - 맨 끝 점 펄스 애니메이션
 * - devicePixelRatio 반영으로 Retina 화면 선명
 *
 * @param {string} canvasId  - canvas 요소 id
 * @param {string} tipId     - 툴팁 div 요소 id
 * @param {Array}  rows      - defectTrend rows: [{time, actual, ...}]
 * @param {number} threshold - 임계값 (기본 4.0)
 */
function renderQaDefectTrendCanvas(canvasId, tipId, rows = [], threshold = 4.0) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  // 이전 RAF 정리
  if (QA_TREND_STATE.raf) {
    cancelAnimationFrame(QA_TREND_STATE.raf);
    QA_TREND_STATE.raf = null;
  }
  QA_TREND_STATE.hoverIdx = -1;
  QA_TREND_STATE.animT = 0;

  // 데이터 없을 때
  if (!rows || !rows.length) {
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width || 400;
    canvas.height = rect.height || 150;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = CHART_TOKENS.muted;
    ctx.font = '12px DM Sans, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('데이터 없음', canvas.width / 2, canvas.height / 2);
    return;
  }

  // 데이터 정렬
  const sorted = [...rows]
    .filter(r => r && r.time != null)
    .sort((a, b) => String(a.time).localeCompare(String(b.time)));

  // 테마 색상 (CHART_TOKENS 활용)
  const COL_NORMAL  = CHART_TOKENS.blue;
  const COL_DANGER  = CHART_TOKENS.red;
  const COL_THRESH  = CHART_TOKENS.thresholdDanger;
  const COL_MUTED   = CHART_TOKENS.muted;
  const COL_GRID    = CHART_TOKENS.grid;

  function getCSSSize() {
    const r = canvas.getBoundingClientRect();
    return { W: r.width, H: r.height };
  }

  function xi(i, IW) {
    return QA_PL + i / (sorted.length - 1) * IW;
  }

  function yi(v, IH) {
    const min = 0, max = Math.max(6, threshold * 1.5);
    return QA_PT + IH - ((v - min) / (max - min)) * IH;
  }

  function draw() {
    QA_TREND_STATE.animT += 0.05;

    const { W, H } = getCSSSize();
    const dpr = window.devicePixelRatio || 1;
    canvas.width  = W * dpr;
    canvas.height = H * dpr;

    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);

    const IW = W - QA_PL - QA_PR;
    const IH = H - QA_PT - QA_PB;
    const thY = yi(threshold, IH);

    // 임계 초과 붉은 영역
    ctx.fillStyle = 'rgba(220,38,38,0.07)';
    ctx.beginPath();
    ctx.moveTo(QA_PL, thY);
    sorted.forEach((d, i) => ctx.lineTo(xi(i, IW), Math.min(yi(Number(d.actual) || 0, IH), thY)));
    ctx.lineTo(W - QA_PR, thY);
    ctx.closePath();
    ctx.fill();

    // 일반 그라디언트 영역
    const grad = ctx.createLinearGradient(0, QA_PT, 0, H - QA_PB);
    grad.addColorStop(0, 'rgba(37,99,235,0.10)');
    grad.addColorStop(1, 'rgba(37,99,235,0.00)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(QA_PL, H - QA_PB);
    sorted.forEach((d, i) => ctx.lineTo(xi(i, IW), yi(Number(d.actual) || 0, IH)));
    ctx.lineTo(W - QA_PR, H - QA_PB);
    ctx.closePath();
    ctx.fill();

    // y축 그리드
    const max = Math.max(6, threshold * 1.5);
    const step = max <= 6 ? 1 : max <= 10 ? 2 : 5;
    for (let v = 0; v <= max; v += step) {
      const vy = yi(v, IH);
      ctx.setLineDash([2, 3]);
      ctx.strokeStyle = COL_GRID;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(QA_PL, vy);
      ctx.lineTo(W - QA_PR, vy);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = COL_MUTED;
      ctx.font = '8px DM Mono, monospace';
      ctx.textAlign = 'right';
      ctx.fillText(v.toFixed(1) + '%', QA_PL - 5, vy + 3);
    }

    // 임계선
    ctx.setLineDash([5, 3]);
    ctx.strokeStyle = COL_THRESH;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(QA_PL, thY);
    ctx.lineTo(W - QA_PR, thY);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = COL_THRESH;
    ctx.font = '8.5px DM Sans, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('임계 ' + threshold.toFixed(1) + '%', W - QA_PR + 4, thY + 3);

    // 세로 커서선
    if (QA_TREND_STATE.hoverIdx >= 0) {
      const cx2 = xi(QA_TREND_STATE.hoverIdx, IW);
      ctx.setLineDash([4, 3]);
      ctx.strokeStyle = 'rgba(90,110,140,0.45)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(cx2, QA_PT);
      ctx.lineTo(cx2, H - QA_PB);
      ctx.stroke();
      ctx.setLineDash([]);
      // 하단 날짜 강조
      ctx.fillStyle = COL_NORMAL;
      ctx.font = 'bold 8px DM Sans, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(String(sorted[QA_TREND_STATE.hoverIdx].time).slice(0, 10), cx2, H - 5);
      // 포인트 강조 링
      const py = yi(Number(sorted[QA_TREND_STATE.hoverIdx].actual) || 0, IH);
      const over = (Number(sorted[QA_TREND_STATE.hoverIdx].actual) || 0) > threshold;
      ctx.beginPath();
      ctx.arc(cx2, py, 8, 0, Math.PI * 2);
      ctx.fillStyle = over ? 'rgba(220,38,38,0.15)' : 'rgba(37,99,235,0.15)';
      ctx.fill();
    }

    // 라인 (임계 초과 구간 빨간색)
    sorted.forEach((d, i) => {
      if (i === 0) return;
      const prev = sorted[i - 1];
      const vCur  = Number(d.actual)    || 0;
      const vPrev = Number(prev.actual) || 0;
      ctx.strokeStyle = vCur > threshold || vPrev > threshold ? COL_DANGER : COL_NORMAL;
      ctx.lineWidth = 2.5;
      ctx.lineJoin = 'round';
      ctx.lineCap  = 'round';
      ctx.beginPath();
      ctx.moveTo(xi(i - 1, IW), yi(vPrev, IH));
      ctx.lineTo(xi(i,     IW), yi(vCur,  IH));
      ctx.stroke();
    });

    // 포인트
    sorted.forEach((d, i) => {
      const isLast = i === sorted.length - 1;
      const isHov  = i === QA_TREND_STATE.hoverIdx;
      const px = xi(i, IW);
      const py = yi(Number(d.actual) || 0, IH);
      const over = (Number(d.actual) || 0) > threshold;

      if (isLast) {
        const pr = 4 + Math.abs(Math.sin(QA_TREND_STATE.animT * 0.8)) * 3;
        ctx.beginPath();
        ctx.arc(px, py, pr, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(220,38,38,0.18)';
        ctx.fill();
        ctx.beginPath();
        ctx.arc(px, py, 4.5, 0, Math.PI * 2);
        ctx.fillStyle = COL_DANGER;
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 2;
        ctx.fill();
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.arc(px, py, isHov ? 6 : 4, 0, Math.PI * 2);
        ctx.fillStyle = isHov ? (over ? COL_DANGER : COL_NORMAL) : 'white';
        ctx.strokeStyle = over ? COL_DANGER : COL_NORMAL;
        ctx.lineWidth = 2;
        ctx.fill();
        ctx.stroke();
      }
    });

    // x축 레이블 (hover 포인트 제외)
    ctx.fillStyle = COL_MUTED;
    ctx.font = '8px DM Sans, sans-serif';
    ctx.textAlign = 'center';
    sorted.forEach((d, i) => {
      if (i !== QA_TREND_STATE.hoverIdx) {
        ctx.fillText(String(d.time).slice(5, 10), xi(i, IW), H - 5);
      }
    });

    QA_TREND_STATE.raf = requestAnimationFrame(draw);
  }

  draw();

  // 마우스 이벤트 — getBoundingClientRect CSS 좌표 기준
  const tip = tipId ? document.getElementById(tipId) : null;

  canvas._qaTrendMoveHandler && canvas.removeEventListener('mousemove', canvas._qaTrendMoveHandler);
  canvas._qaTrendLeaveHandler && canvas.removeEventListener('mouseleave', canvas._qaTrendLeaveHandler);

  canvas._qaTrendMoveHandler = function(e) {
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const IW = rect.width - QA_PL - QA_PR;

    let closest = -1, minDist = 9999;
    sorted.forEach((d, i) => {
      const dist = Math.abs((QA_PL + i / (sorted.length - 1) * IW) - mouseX);
      if (dist < minDist) { minDist = dist; closest = i; }
    });

    if (minDist < 50) {
      QA_TREND_STATE.hoverIdx = closest;
      if (tip) {
        const d    = sorted[closest];
        const val  = Number(d.actual) || 0;
        const over = val > threshold;

        // 날짜
        const dateEl = tip.querySelector('.qa-tip-date');
        const valEl  = tip.querySelector('.qa-tip-val');
        const stEl   = tip.querySelector('.qa-tip-status');
        if (dateEl) dateEl.textContent = String(d.time).slice(0, 10);
        if (valEl)  { valEl.textContent = val.toFixed(2) + '%'; valEl.style.color = over ? 'var(--danger)' : 'var(--accent)'; }
        if (stEl)   { stEl.textContent = over ? '⚠ 임계 초과' : '✓ 정상 범위'; stEl.style.color = over ? 'var(--danger)' : 'var(--status-run)'; }

        const IW2 = rect.width - QA_PL - QA_PR;
        const cx2 = QA_PL + closest / (sorted.length - 1) * IW2;
        let left = cx2 + 16;
        if (left + 150 > rect.width) left = cx2 - 166;
        tip.style.left = Math.max(0, left) + 'px';
        tip.classList.add('show');
      }
    } else {
      QA_TREND_STATE.hoverIdx = -1;
      if (tip) tip.classList.remove('show');
    }
  };

  canvas._qaTrendLeaveHandler = function() {
    QA_TREND_STATE.hoverIdx = -1;
    if (tip) tip.classList.remove('show');
  };

  canvas.addEventListener('mousemove', canvas._qaTrendMoveHandler);
  canvas.addEventListener('mouseleave', canvas._qaTrendLeaveHandler);
}
