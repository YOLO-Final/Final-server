#!/usr/bin/env bash
set -euo pipefail

# =========================
# 설정
# =========================
CONTAINER_NAME="final_project_rss_postgres"
OUTPUT_DIR="./db_inventory"
TS="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$OUTPUT_DIR"

echo "[1/8] PostgreSQL 접속 정보 확인 중..."
ENV_DUMP="$(docker exec "$CONTAINER_NAME" sh -c 'env | grep ^POSTGRES_ || true')"

POSTGRES_USER="$(echo "$ENV_DUMP" | grep '^POSTGRES_USER=' | head -1 | cut -d= -f2- || true)"
POSTGRES_DB="$(echo "$ENV_DUMP" | grep '^POSTGRES_DB=' | head -1 | cut -d= -f2- || true)"

if [ -z "${POSTGRES_USER:-}" ]; then
  POSTGRES_USER="postgres"
fi

if [ -z "${POSTGRES_DB:-}" ]; then
  POSTGRES_DB="postgres"
fi

echo "  - CONTAINER_NAME=$CONTAINER_NAME"
echo "  - POSTGRES_USER=$POSTGRES_USER"
echo "  - POSTGRES_DB=$POSTGRES_DB"

run_sql() {
  local sql="$1"
  docker exec -i "$CONTAINER_NAME" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off -F $'\t' -At -c "$sql"
}

run_sql_pretty() {
  local sql="$1"
  docker exec -i "$CONTAINER_NAME" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off -c "$sql"
}

echo "[2/8] DB/스키마/테이블 목록 추출 중..."
run_sql_pretty "\l" > "$OUTPUT_DIR/${TS}_databases.txt"
run_sql_pretty "\dn" > "$OUTPUT_DIR/${TS}_schemas.txt"
run_sql_pretty "\dt *.*" > "$OUTPUT_DIR/${TS}_all_tables.txt"

echo "[3/8] public 스키마 테이블 목록 CSV 추출 중..."
run_sql "
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;
" > "$OUTPUT_DIR/${TS}_table_list.tsv"

echo "[4/8] 테이블별 row 수 추출 중..."
TABLES=$(run_sql "
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;
")

ROWCOUNT_FILE="$OUTPUT_DIR/${TS}_table_row_counts.tsv"
echo -e "table_name\trow_count" > "$ROWCOUNT_FILE"

while IFS= read -r table; do
  [ -z "$table" ] && continue
  count=$(run_sql "SELECT COUNT(*) FROM public.\"$table\";")
  echo -e "${table}\t${count}" >> "$ROWCOUNT_FILE"
done <<< "$TABLES"

echo "[5/8] 전체 컬럼 목록 추출 중..."
run_sql "
SELECT
  table_name,
  ordinal_position,
  column_name,
  data_type,
  is_nullable,
  COALESCE(column_default, '') AS column_default
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
" > "$OUTPUT_DIR/${TS}_columns.tsv"

echo "[6/8] PK/FK 관계 추출 중..."
run_sql "
SELECT
  tc.table_name,
  kcu.column_name,
  tc.constraint_type,
  COALESCE(ccu.table_name, '') AS foreign_table_name,
  COALESCE(ccu.column_name, '') AS foreign_column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema = kcu.table_schema
LEFT JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name
 AND ccu.table_schema = tc.table_schema
WHERE tc.table_schema = 'public'
  AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
ORDER BY tc.table_name, tc.constraint_type, kcu.column_name;
" > "$OUTPUT_DIR/${TS}_constraints.tsv"

echo "[7/8] 샘플 데이터 추출 중..."
SAMPLE_TABLES="
production_logs
defect_logs
lines
product_models
equipment
notifications
ml_predictions
inspection_results
"

for table in $SAMPLE_TABLES; do
  exists=$(run_sql "
  SELECT COUNT(*)
  FROM information_schema.tables
  WHERE table_schema = 'public'
    AND table_name = '$table';
  ")
  if [ "$exists" = "1" ]; then
    run_sql_pretty "SELECT * FROM public.\"$table\" LIMIT 5;" > "$OUTPUT_DIR/${TS}_sample_${table}.txt"
  fi
done

echo "[8/8] Markdown 보고서 생성 중..."
REPORT_MD="$OUTPUT_DIR/${TS}_db_inventory_report.md"

{
  echo "# DB 인벤토리 점검 보고서"
  echo
  echo "- 생성 시각: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "- 컨테이너: \`$CONTAINER_NAME\`"
  echo "- DB 유저: \`$POSTGRES_USER\`"
  echo "- DB 이름: \`$POSTGRES_DB\`"
  echo

  echo "## 1. 테이블 목록"
  echo
  echo "| 테이블명 | row 수 |"
  echo "|---|---:|"
  tail -n +2 "$ROWCOUNT_FILE" | while IFS=$'\t' read -r table row_count; do
    echo "| $table | $row_count |"
  done
  echo

  echo "## 2. 핵심 컬럼 목록"
  echo
  echo "> 전체 원본은 \`${TS}_columns.tsv\` 참고"
  echo
  echo "| 테이블명 | 순서 | 컬럼명 | 타입 | NULL 허용 | 기본값 |"
  echo "|---|---:|---|---|---|---|"
  head -n 200 "$OUTPUT_DIR/${TS}_columns.tsv" | while IFS=$'\t' read -r table pos col dtype nullable def; do
    echo "| $table | $pos | $col | $dtype | $nullable | ${def:-} |"
  done
  echo

  echo "## 3. 조인 관계(PK/FK)"
  echo
  echo "| 기준 테이블 | 조인 컬럼 | 제약조건 | 대상 테이블 | 대상 컬럼 |"
  echo "|---|---|---|---|---|"
  cat "$OUTPUT_DIR/${TS}_constraints.tsv" | while IFS=$'\t' read -r table col ctype ftable fcol; do
    echo "| $table | $col | $ctype | ${ftable:-} | ${fcol:-} |"
  done
  echo

  echo "## 4. 시각화 검토용 우선 테이블"
  echo
  echo "- 1차 우선 확인 후보"
  echo "  - \`production_logs\`"
  echo "  - \`defect_logs\`"
  echo "  - \`lines\`"
  echo "  - \`product_models\`"
  echo
  echo "- 2차 확인 후보"
  echo "  - \`equipment\`"
  echo "  - \`notifications\`"
  echo "  - \`ml_predictions\`"
  echo "  - \`inspection_results\`"
  echo
  echo "## 5. 다음 작업"
  echo
  echo "1. \`${TS}_columns.tsv\`에서 시간 컬럼, 상태 컬럼, 수량 컬럼, 분류 컬럼을 체크"
  echo "2. \`${TS}_constraints.tsv\`에서 조인 가능 관계 확인"
  echo "3. 샘플 파일(\`${TS}_sample_*.txt\`)로 실제 값 형태 확인"
  echo "4. 이를 바탕으로 아래 4개 표를 최종 정리"
  echo "   - 테이블 목록"
  echo "   - 핵심 컬럼 목록"
  echo "   - 조인 관계"
  echo "   - 시각화 가능 항목"
} > "$REPORT_MD"

echo
echo "완료:"
echo "  - 보고서(MD): $REPORT_MD"
echo "  - 테이블 목록: $OUTPUT_DIR/${TS}_table_list.tsv"
echo "  - row 수:      $OUTPUT_DIR/${TS}_table_row_counts.tsv"
echo "  - 컬럼 목록:   $OUTPUT_DIR/${TS}_columns.tsv"
echo "  - 제약조건:    $OUTPUT_DIR/${TS}_constraints.tsv"
echo "  - 샘플 데이터: $OUTPUT_DIR/${TS}_sample_*.txt"