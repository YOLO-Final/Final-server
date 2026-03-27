/* ============================================================
   dashboard_detail_views.js — 상세 모달 뷰
   ============================================================ */
'use strict';

/*
 * 이 파일의 역할
 * 1. 상세 모달의 열기/닫기/본문 렌더를 담당한다.
 * 2. 현재는 범용 key-value 형태의 단순 상세 보기를 제공한다.
 * 3. 특정 탭별 상세 템플릿이 늘어나면 이 파일이 확장 포인트가 된다.
 */

const DETAIL_VIEWS = {
  // 과거 단순 모달 경로.
  // 현재 메인 상세 흐름은 openDashboardDetailModal(detail API)이지만,
  // 목록형 전체 보기나 임시 상세를 붙일 때는 아직 이 경로를 재사용할 수 있다.
  /* 외부에서 상세 데이터를 넘기면 모달을 열고 내용을 채운다. */
  open(data) {
    const modal = document.getElementById('detailModal');
    const content = document.getElementById('detailModalContent');
    if (!modal || !content) return;
    content.innerHTML = this.render(data);
    modal.classList.add('open');
  },

  /* 열려 있는 상세 모달을 닫는다. */
  close() {
    const modal = document.getElementById('detailModal');
    if (modal) modal.classList.remove('open');
  },

  /*
   * 현재 렌더 규칙
   * - 입력은 단순 객체(dict)라고 가정한다.
   * - type 같은 내부 메타 키는 화면에서 숨긴다.
   * - 나머지는 "라벨 / 값" 2열 행으로 풀어낸다.
   * - 값이 비어 있으면 '-'로 대체해서 빈칸처럼 보이지 않게 한다.
   *
   * 향후 확장 방향
   * - detailId별 전용 템플릿
   * - 상태 배지 / 심각도 색상
   * - 표 형태 로그 / 연관 항목 카드
   */
  render(data) {
    if (!data) return '<p class="empty-msg">데이터 없음</p>';
    const rows = Object.entries(data)
      .filter(([k]) => !['type'].includes(k))
      .map(([k, v]) => `
        <div class="modal-row">
          <span class="modal-label">${k}</span>
          <span class="modal-val">${v ?? '-'}</span>
        </div>`).join('');
    return rows;
  },
};

// 모달 초기화: 배경 클릭 시 닫히도록 기본 이벤트를 건다.
document.addEventListener('DOMContentLoaded', () => {
  const backdrop = document.getElementById('detailModal');
  if (backdrop) {
    backdrop.addEventListener('click', e => {
      if (e.target === backdrop) DETAIL_VIEWS.close();
    });
  }
});
