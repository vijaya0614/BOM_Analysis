# TODO — Fix all errors and loose ends

## Web Frontend (TypeScript build errors)
- [x] Track build errors
- [x] Fix `App.tsx:67` — remove unused `handleSelectComponentById`
- [x] Fix `ComponentDetailPage.tsx:201-208` — wrap `unknown` spec values in `String()`
- [x] Fix `DashboardPage.tsx:122` — remove unused `needsAttention`
- [x] Fix `ReportDownloadPage.tsx:167,216` — remove unused `approvedCount`/`approvedEntries`
- [x] Reorganize `ThemeContext.tsx` to clear fast-refresh lint warning (move `useTheme` to separate file)
- [x] Reorganize `HardwareTwinContext.tsx` to clear fast-refresh lint warning (move `useHardwareTwin` to separate file)
- [x] Verify `npm run build` passes cleanly
- [x] Verify `npm run lint` has no errors/warnings

## Verification
- [x] Run Python unit tests (all pass)
- [x] Final review
