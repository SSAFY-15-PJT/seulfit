# Frontend Handoff

## Current branch
- Branch: `local/frontend-demo`
- Latest pushed commit: `9475593 feat: refresh map and dashboard card ui`
- Remote branch exists on `origin`

## What is already in place
- `MapView.vue`
  - Map functionality is preserved.
  - Recommendation area is shown under the map.
  - Credit / debit tabs switch correctly.
  - Featured card view uses `object-fit: contain` so card images are not cropped.
  - Recommendation detail now shows more benefit-related lines.
  - Login session UI is placed in the map page sidebar, not in profile.
  - Category chips use emoji icons and no longer show credit/debit counts.
  - `추천 결과 자세히보기` routes to `/dashboard`.

- `DashboardView.vue`
  - Category chips were updated to match the same icon-based style.
  - Credit / debit ranking layout is still intact.
  - Category-specific ranking and overview sections are still functional.

- `AppNav.vue`
  - Global `SeulPick` brand was made larger in the top header.

- `styles.css`
  - Global visual tone is adjusted toward a cleaner bank/card-site style.
  - Shared chip, badge, panel, and featured-card styles were updated.

## Important files
- `frontend/src/views/MapView.vue`
- `frontend/src/views/DashboardView.vue`
- `frontend/src/components/AppNav.vue`
- `frontend/src/styles.css`

## Notes for the next session
- Do not touch root `README.md` unless explicitly asked.
- `reference/` is untracked and intentionally left alone.
- If you change the map layout, keep the login block inside the map sidebar.
- If you change category chips, keep the emoji/icon-only style aligned between map and dashboard.
- If you need to verify visuals, run the frontend from `frontend/` with `npm run dev`.

## Suggested next checks
- Open the map page and verify the sidebar login block still sits above weather / summary.
- Open the dashboard and verify the category chips still use the icon layout.
- Check that the larger brand text does not break the navbar on smaller widths.
