BEGIN;

-- wed_dashboard.employees 기준으로 user_table 계정을 생성/동기화한다.
-- 초기 비밀번호는 legacy sha256("1234") 해시를 사용한다.
-- plain: 1234
-- sha256: 03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4
INSERT INTO public.lines (line_id, line_name, status, current_model_id)
VALUES
  (1, 'LINE-A', 'active', NULL),
  (2, 'LINE-B', 'active', NULL),
  (3, 'LINE-C', 'active', NULL),
  (4, 'LINE-D', 'active', NULL)
ON CONFLICT (line_id) DO UPDATE
SET
  line_name = COALESCE(NULLIF(public.lines.line_name, ''), EXCLUDED.line_name),
  status = COALESCE(NULLIF(public.lines.status, ''), EXCLUDED.status);

WITH src AS (
    SELECT
        e.employee_no,
        e.employee_name,
        CASE
            WHEN lower(COALESCE(e.role_code, '')) IN ('operator', 'worker') THEN 'worker'
            WHEN lower(COALESCE(e.role_code, '')) IN ('qa', 'quality_manager') THEN 'quality_manager'
            WHEN lower(COALESCE(e.role_code, '')) IN ('manager') THEN 'manager'
            WHEN lower(COALESCE(e.role_code, '')) IN ('maintenance') THEN 'user'
            ELSE 'user'
        END AS mapped_role,
        e.line_id AS wd_line_id,
        COALESCE(e.is_active, TRUE) AS is_active
    FROM wed_dashboard.employees e
)
INSERT INTO public.user_table (
    employee_no,
    password_hash,
    id_active,
    id_locked,
    login_fail_count,
    token_version,
    join_date,
    last_login,
    role,
    name,
    line_id
)
SELECT
    s.employee_no,
    '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4',
    s.is_active,
    FALSE,
    0,
    0,
    NOW(),
    NULL,
    s.mapped_role,
    s.employee_name,
    s.wd_line_id
FROM src s
ON CONFLICT (employee_no) DO UPDATE
SET
    role = EXCLUDED.role,
    name = EXCLUDED.name,
    line_id = EXCLUDED.line_id,
    id_active = EXCLUDED.id_active;

COMMIT;
