# DB 인벤토리 점검 보고서

- 생성 시각: 2026-03-14 15:03:42
- 컨테이너: `final_project_rss_postgres`
- DB 유저: `FP_ADMIN`
- DB 이름: `Final_Project_DB`

## 1. 테이블 목록

| 테이블명 | row 수 |
|---|---:|
| defect_logs | 0 |

## 2. 핵심 컬럼 목록

> 전체 원본은 `20260314_150341_columns.tsv` 참고

| 테이블명 | 순서 | 컬럼명 | 타입 | NULL 허용 | 기본값 |
|---|---:|---|---|---|---|
| defect_logs | 1 | defect_id | integer | NO | nextval('defect_logs_defect_id_seq'::regclass) |
| defect_logs | 2 | line_id | integer | NO |  |
| defect_logs | 3 | model_id | character varying | NO |  |
| defect_logs | 4 | detected_by | character varying | YES |  |
| defect_logs | 5 | defect_class | character varying | YES |  |
| defect_logs | 6 | inspection_qty | integer | YES |  |
| defect_logs | 7 | good_qty | integer | YES |  |
| defect_logs | 8 | recorded_at | timestamp without time zone | YES |  |
| defect_logs | 9 | defect_qty | integer | YES |  |
| defect_type | 1 | class_id | character varying | YES |  |
| defect_type | 2 | class_name | character varying | YES |  |
| defect_type | 3 | desc | character varying | YES |  |
| environment_logs | 1 | env_id | integer | NO | nextval('environment_logs_env_id_seq'::regclass) |
| environment_logs | 2 | line_id | integer | YES |  |
| environment_logs | 3 | temperature | double precision | YES |  |
| environment_logs | 4 | humidity | double precision | YES |  |
| environment_logs | 5 | recorded_at | timestamp without time zone | YES |  |
| equipment | 1 | equipment_id | integer | NO | nextval('equipment_equipment_id_seq'::regclass) |
| equipment | 2 | equipment_name | character varying | YES |  |
| equipment | 3 | status | character varying | YES |  |
| equipment | 4 | last_checked_at | timestamp without time zone | YES |  |
| equipment | 5 | line_id | integer | YES |  |
| face_embedding_table | 1 | employee_no | character varying | NO |  |
| face_embedding_table | 2 | embedding_json | character varying | NO |  |
| face_embedding_table | 3 | embedding_id | integer | NO | nextval('face_embedding_table_embedding_id_seq'::regclass) |
| items | 1 | id | integer | NO | nextval('items_id_seq'::regclass) |
| items | 2 | title | character varying | NO |  |
| items | 3 | description | character varying | YES |  |
| lines | 1 | line_id | integer | NO | nextval('lines_line_id_seq'::regclass) |
| lines | 2 | line_name | character varying | YES |  |
| lines | 3 | status | character varying | YES |  |
| lines | 4 | current_model_id | character varying | YES |  |
| ml_predictions | 1 | pred_id | integer | NO | nextval('ml_predictions_pred_id_seq'::regclass) |
| ml_predictions | 2 | line_id | integer | NO | nextval('ml_predictions_line_id_seq'::regclass) |
| ml_predictions | 3 | pred_type | character varying | YES |  |
| ml_predictions | 4 | predicted_value | double precision | YES |  |
| ml_predictions | 5 | predicted_at | timestamp without time zone | YES |  |
| ml_predictions | 6 | valid_until | timestamp without time zone | YES |  |
| notifications | 1 | noti_id | integer | NO | nextval('notifications_noti_id_seq'::regclass) |
| notifications | 2 | line_id | integer | YES |  |
| notifications | 3 | target_role | character varying | YES |  |
| notifications | 4 | level | integer | YES |  |
| notifications | 5 | message | character varying | YES |  |
| notifications | 6 | triggered_at | timestamp without time zone | YES |  |
| notifications | 7 | expires_at | timestamp without time zone | YES |  |
| notifications | 8 | is_dismissed | boolean | YES |  |
| product_models | 2 | model_name | character varying | YES |  |
| product_models | 3 | alert_threshold | double precision | YES |  |
| product_models | 4 | danger_threshold | double precision | YES |  |
| product_models | 5 | unit | character varying | YES |  |
| product_models | 6 | model_id | character varying | NO |  |
| production_logs | 1 | log_id | bigint | NO | nextval('production_logs_log_id_seq'::regclass) |
| production_logs | 2 | line_id | integer | NO |  |
| production_logs | 3 | model_id | character varying | NO |  |
| production_logs | 4 | produced_qty | integer | YES |  |
| user_table | 1 | employee_no | character varying | NO |  |
| user_table | 2 | password_hash | character varying | YES |  |
| user_table | 3 | id_active | boolean | YES |  |
| user_table | 4 | id_locked | boolean | YES |  |
| user_table | 5 | login_fail_count | bigint | YES |  |
| user_table | 6 | token_version | bigint | YES |  |
| user_table | 7 | join_date | timestamp without time zone | YES |  |
| user_table | 8 | last_login | timestamp without time zone | YES |  |
| user_table | 9 | role | character varying | YES |  |
| user_table | 10 | name | character varying | YES |  |
| user_table | 12 | line_id | integer | NO | nextval('user_table_line_id_seq'::regclass) |
| vector_table | 1 | employee_no | character varying | YES |  |
| vector_table | 2 | face_embedding | tsvector | YES |  |
| vision_result | 1 | id | integer | YES |  |
| vision_result | 2 | request_id | character varying | YES |  |
| vision_result | 3 | image_path | character varying | YES |  |
| vision_result | 4 | result_status | character varying | YES |  |
| vision_result | 5 | defect_type | character varying | YES |  |
| vision_result | 6 | confidence | double precision | YES |  |
| vision_result | 7 | created_at | date | YES |  |

## 3. 조인 관계(PK/FK)

| 기준 테이블 | 조인 컬럼 | 제약조건 | 대상 테이블 | 대상 컬럼 |
|---|---|---|---|---|
| defect_logs | detected_by | FOREIGN KEY | user_table | employee_no |
| defect_logs | line_id | FOREIGN KEY | lines | line_id |
| defect_logs | model_id | FOREIGN KEY | product_models | model_id |
| defect_logs | defect_id | PRIMARY KEY | defect_logs | defect_id |
| environment_logs | line_id | FOREIGN KEY | lines | line_id |
| equipment | line_id | FOREIGN KEY | lines | line_id |
| face_embedding_table | employee_no | FOREIGN KEY | user_table | employee_no |
| face_embedding_table | employee_no | PRIMARY KEY | face_embedding_table | employee_no |
| items | id | PRIMARY KEY | items | id |
| lines | current_model_id | FOREIGN KEY | product_models | model_id |
| lines | line_id | PRIMARY KEY | lines | line_id |
| ml_predictions | line_id | FOREIGN KEY | lines | line_id |
| notifications | line_id | FOREIGN KEY | lines | line_id |
| product_models | model_id | PRIMARY KEY | product_models | model_id |
| production_logs | line_id | FOREIGN KEY | lines | line_id |
| production_logs | model_id | FOREIGN KEY | product_models | model_id |
| production_logs | log_id | PRIMARY KEY | production_logs | log_id |
| user_table | line_id | FOREIGN KEY | lines | line_id |
| user_table | employee_no | PRIMARY KEY | user_table | employee_no |
| vector_table | employee_no | FOREIGN KEY | user_table | employee_no |

## 4. 시각화 검토용 우선 테이블

- 1차 우선 확인 후보
  - `production_logs`
  - `defect_logs`
  - `lines`
  - `product_models`

- 2차 확인 후보
  - `equipment`
  - `notifications`
  - `ml_predictions`
  - `inspection_results`

## 5. 다음 작업

1. `20260314_150341_columns.tsv`에서 시간 컬럼, 상태 컬럼, 수량 컬럼, 분류 컬럼을 체크
2. `20260314_150341_constraints.tsv`에서 조인 가능 관계 확인
3. 샘플 파일(`20260314_150341_sample_*.txt`)로 실제 값 형태 확인
4. 이를 바탕으로 아래 4개 표를 최종 정리
   - 테이블 목록
   - 핵심 컬럼 목록
   - 조인 관계
   - 시각화 가능 항목
