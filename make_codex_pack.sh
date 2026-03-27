#!/bin/bash
set -e

echo "[1/4] folder structure..."
tree -a \
-I '__pycache__|.git|node_modules|.venv|venv|*.pyc|*.pyo|*.log|*.jpg|*.jpeg|*.png|*.pt|server.crt|server.key' \
> folder_structure_with_files.txt

echo "[2/4] docs pack..."
{
  echo "===== FILE: docs/9.2.2 역할별 화면 목적 정리.md ====="
  cat "docs/9.2.2 역할별 화면 목적 정리.md"
  echo

  echo "===== FILE: docs/9.2.3 공용 레이아웃 및 컴포넌트 정리.md ====="
  cat "docs/9.2.3 공용 레이아웃 및 컴포넌트 정리.md"
  echo

  echo "===== FILE: docs/9.5.1 KPI 정의서.md ====="
  cat "docs/9.5.1 KPI 정의서.md"
  echo

  echo "===== FILE: docs/9.5.2 최종 차트 유형 선정서.md ====="
  cat "docs/9.5.2 최종 차트 유형 선정서.md"
  echo

  echo "===== FILE: docs/9.5.3.1_차트테이블_구현_대상_목록.md ====="
  cat "docs/9.5.3.1_차트테이블_구현_대상_목록.md"
  echo

  echo "===== FILE: docs/9.5.3.2 공통 UI 규칙 정의.md ====="
  cat "docs/9.5.3.2 공통 UI 규칙 정의.md"
  echo

  echo "===== FILE: docs/9.5.3.3_KPI카드_구현메모.md ====="
  cat "docs/9.5.3.3_KPI카드_구현메모.md"
  echo

  echo "===== FILE: docs/9.5.3.4_상태표현_구현메모.md ====="
  cat "docs/9.5.3.4_상태표현_구현메모.md"
  echo

  echo "===== FILE: docs/9.5.3.5_라인차트_구현메모.md ====="
  cat "docs/9.5.3.5_라인차트_구현메모.md"
  echo

  echo "===== FILE: docs/9.5.3.6_바차트_구현메모.md ====="
  cat "docs/9.5.3.6_바차트_구현메모.md"
  echo

  echo "===== FILE: docs/9.5.3.7_도넛차트_구현메모.md ====="
  cat "docs/9.5.3.7_도넛차트_구현메모.md"
  echo

  echo "===== FILE: docs/9.5.3.8_로그리스트_구현메모.md ====="
  cat "docs/9.5.3.8_로그리스트_구현메모.md"
  echo

  echo "===== FILE: docs/9.5.3.9_상세테이블_구현메모.md ====="
  cat "docs/9.5.3.9_상세테이블_구현메모.md"
  echo

  echo "===== FILE: docs/9.5.3.10_차트공통유틸_정리.md ====="
  cat "docs/9.5.3.10_차트공통유틸_정리.md"
  echo
} > for_codex_docs_pack.txt

echo "[3/4] code pack..."
{
  echo "===== FILE: nginx/html/js/wed_dashboard/dashboard_api.js ====="
  nl -ba nginx/html/js/wed_dashboard/dashboard_api.js
  echo

  echo "===== FILE: nginx/html/js/wed_dashboard/dashboard_app.js ====="
  nl -ba nginx/html/js/wed_dashboard/dashboard_app.js
  echo

  echo "===== FILE: nginx/html/css/wed_dashboard/dashboard_style.css ====="
  nl -ba nginx/html/css/wed_dashboard/dashboard_style.css
  echo

  echo "===== FILE: nginx/html/js/wed_dashboard/dashboard_charts.js ====="
  nl -ba nginx/html/js/wed_dashboard/dashboard_charts.js
  echo

  echo "===== FILE: nginx/html/web_dashboard.html ====="
  nl -ba nginx/html/web_dashboard.html
  echo

  echo "===== FILE: server_api/src/modules/dashboard/service.py ====="
  nl -ba server_api/src/modules/dashboard/service.py
  echo

  echo "===== FILE: server_api/src/modules/dashboard/router.py ====="
  nl -ba server_api/src/modules/dashboard/router.py
  echo

  echo "===== FILE: DB_Structure.erd ====="
  nl -ba DB_Structure.erd
  echo
} > for_codex_code_pack.txt

echo "[4/4] full pack..."
{
  echo "=============================="
  echo "PROJECT STRUCTURE"
  echo "=============================="
  cat folder_structure_with_files.txt
  echo

  echo "=============================="
  echo "DOCS PACK"
  echo "=============================="
  cat for_codex_docs_pack.txt
  echo

  echo "=============================="
  echo "CODE PACK"
  echo "=============================="
  cat for_codex_code_pack.txt
  echo
} > for_codex_full_pack.txt

echo "done:"
echo " - folder_structure_with_files.txt"
echo " - for_codex_docs_pack.txt"
echo " - for_codex_code_pack.txt"
echo " - for_codex_full_pack.txt"
