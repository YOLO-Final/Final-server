# COMMON Module (Code)

## 목적
여러 모듈에서 공통으로 사용할 RBAC/Audit 유틸 뼈대를 제공합니다.

## 핵심 파일
- `server_api/src/modules/common/rbac.py`
- `server_api/src/modules/common/audit.py`

## 현재 상태
- placeholder 중심 구현
- 실제 정책/저장 로직은 향후 auth/DB와 결합 필요

## 확장 가이드
- RBAC: role 검증 -> 권한 매트릭스 -> 라우트 데코레이터/Depends 형태로 확장
- Audit: actor/action + request_id + timestamp + resource_id 표준화 권장
