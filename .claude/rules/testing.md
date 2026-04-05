# Testing Rules

- Prefer RED-GREEN-REFACTOR for behavior changes:
  - RED: add or update a test that fails for the current behavior.
  - GREEN: implement the minimal code change to pass.
  - REFACTOR: clean up while keeping tests green.
- Prefer focused checks for changed scope before running full-suite checks.
- For bug fixes, reproduce the failure first when practical, then verify the fix.
- If tests are unavailable, provide a concrete manual verification checklist in the final summary.
