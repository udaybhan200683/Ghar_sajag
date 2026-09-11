# Parivar Sathi v3.3.5 — UI test alignment

The functional rule behavior is unchanged.

Updated UI-facing validation after the dashboard hierarchy change:
- Overall banner is tested as generic household status only.
- Morning Routine is explicitly tested as the first routine card before I am OK.
- Added browser coverage for a real missing-morning alert:
  generic red banner + red Morning Routine card with the specific issue.
- Renamed browser test descriptions so they no longer imply the specific problem
  text belongs inside the main banner.
- Added manual UI regression checks UI-01 through UI-07.

Canonical domain-functional scenarios remain 85; these are presentation/browser
checks layered on top of them.
