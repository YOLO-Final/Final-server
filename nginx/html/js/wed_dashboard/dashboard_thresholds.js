/* ============================================================
   dashboard_thresholds.js — 임계값 정의
   ============================================================ */
'use strict';

/*
 * 이 파일의 역할
 * 1. KPI별 warning / critical 기준값을 모아둔다.
 * 2. 값이 높을수록 나쁜지, 낮을수록 나쁜지 판단 규칙을 감춘다.
 * 3. 렌더 파일은 숫자만 넘기고 상태 판정은 여기서 공통 처리한다.
 */

const DASHBOARD_THRESHOLDS = {
  // worker / qa / manager 핵심 KPI에만 우선 적용한다.
  worker_recent_10m_ng: { warning: 10, critical: 15 },
  qa_defect_rate:       { warning: 2.0, critical: 4.0 },
  mgr_oee:              { warning: 75, critical: 65 },
  mgr_achievement:      { warning: 80, critical: 65 },

  // KPI key에 맞는 기준값 묶음을 돌려준다.
  resolveThreshold(key) {
    return this[key] || { warning: null, critical: null };
  },

  // 실제 값 하나를 받아 ok / warning / critical 중 하나로 평가한다.
  evaluate(key, value) {
    const t = this.resolveThreshold(key);
    const v = Number(value);
    if (t.critical != null) {
      if (key === 'mgr_oee' || key === 'mgr_achievement') {
        // 관리자 KPI 일부는 생산성과 달리 값이 낮아질수록 더 위험하다.
        if (v <= t.critical) return 'critical';
        if (v <= t.warning)  return 'warning';
        return 'ok';
      }
      // 나머지 KPI는 값이 올라갈수록 위험이 커지는 기본 규칙을 따른다.
      if (v >= t.critical) return 'critical';
      if (v >= t.warning)  return 'warning';
      return 'ok';
    }
    return 'ok';
  },
};
