# Web Dashboard Structure

`web_dashboard` is split by responsibility so maintenance stays local.

## JavaScript

- `dashboard_app.js`
  App shell. Initializes the page, binds events, switches tabs, and coordinates rendering.
- `dashboard_session.js`
  Session check and logged-in user profile display.
- `dashboard_permissions.js`
  Role normalization, allowed tabs, and tab access control.
- `dashboard_ui.js`
  Shared UI helpers such as notice/ticker and compare panels.
- `dashboard_kpi.js`
  Shared KPI card rendering helpers.
- `dashboard_detail_views.js`
  Shared modal/detail rendering helpers.
- `dashboard_charts.js`
  Shared chart builders and update helpers.
- `dashboard_worker.js`
  Worker tab rendering.
- `dashboard_qa.js`
  QA tab rendering.
- `dashboard_manager.js`
  Manager tab rendering.
- `dashboard_promo.js`
  Promo tab rendering.

## CSS

- `dashboard_style.css`
  Shared layout, cards, typography, and reusable components.
- `dashboard_worker.css`
  Worker-only layout and responsive rules.
- `dashboard_qa.css`
  QA-only layout and responsive rules.
- `dashboard_manager.css`
  Manager-only layout and responsive rules.
- `dashboard_promo.css`
  Promo-only layout and responsive rules.
- `dashboard_status.css`
  Shared status badge styles.

## Editing Rule Of Thumb

- If a change affects one tab only, edit that tab's dedicated JS/CSS file first.
- If a change affects every tab, edit the shared base file first.
- Keep shared helpers in shared files instead of re-adding logic inside role files.
- Preserve the current load order in `web_dashboard.html` when adding new files.
