# Browser compatibility report

## Scope and result

Applied shared compatibility styling to every page template, including public pages, contractor and administrator screens, policy documents and HTTP error pages. Fixed missing mobile markup on privacy/terms pages. Added shrinkable grid/form children, wrapping for long content and setup URLs, responsive logos, scroll-contained reports, visible focus states, readable native form controls, reduced-motion handling and forced-color borders. Native page zoom remains available.

Replaced the administration page's runtime Tailwind CDN with local CSS. Other page templates already use local or inline styles. The enhanced homeowner request no longer requires Object.fromEntries and checks required features before hiding any form sections. If enhancement is unavailable, the native POST form remains usable. HTTP error pages retain status codes and Allow headers; API errors remain JSON.

## Verification

- 22 Python automated tests passed, including page-family mobile markup checks, form flows and HTTP error response contracts.
- Three JavaScript feature-fallback checks passed: missing fetch, missing FormData iteration and missing native validation UI. Run `node tests/browser-fallbacks.cjs` from the repository root.
- Both external JavaScript files passed Node syntax checks.
- Chromium preview: 33 page routes at 320, 768 and 1440 requested viewport widths, totaling 99 geometry checks. No page-level horizontal overflow. Narrow tables intentionally scroll within a container.
- Routes include all ten service pages, all four legacy landing pages, registration aliases, policy pages, login/setup screens, Minnesota/national public pages, request receipt, 404 page, administrator screens and an authenticated contractor dashboard with synthetic long-content records.
- Mobile homeowner submission completed successfully against a local in-memory database. No production records or external messages were used.

## Browser matrix

| Browser / platform | Status |
| --- | --- |
| Chromium in-app preview, desktop and responsive viewports | Layout and homeowner submission tested |
| Chrome and Edge installations | Not separately tested |
| Brave and Opera | Not separately tested |
| Firefox desktop / Android | Not executed in this environment |
| Safari macOS / iPhone / iPad | Not executed in this environment |
| Chrome Android / Samsung Internet / physical touch devices | Not executed in this environment |

Responsive viewport checks are not physical-device tests. Do not label this a complete cross-browser certification. Current popular browsers are the compatibility target; obsolete Internet Explorer is not a supported target. Before release, run the core request, signup, login, setup-link, admin-review and lead-action flows on current Chrome, Edge, Firefox, Safari/iOS and Android browsers, with portrait/landscape, zoom and keyboard navigation.

## References

The grid minimum-size fix follows [MDN's min-width reference](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/min-width). Form enhancement falls back to ordinary submission when [native reportValidity](https://developer.mozilla.org/en-US/docs/Web/API/HTMLTextAreaElement/reportValidity) is unavailable. These references inform implementation; they do not replace browser execution.

## Consumer tracking update

The new status page, receipt link, homepage navigation and administrator consumer-email history passed 27 Chromium state/viewport checks at 320, 768 and 1440 pixels, with no horizontal overflow. Contact actions appeared only for an eligible accepted match. Tracking is server rendered and requires no JavaScript. Other browser engines and physical devices remain unverified.

## Consumer stop-matching control

The confirmation page, cancelled status and administrator history passed nine additional Chromium checks at 320/768/1440 without horizontal overflow. Browser execution verified Keep matching leaves the request open and a confirmed submission changes it to Cancelled. The control uses server-rendered forms, native confirmation validation, CSRF and POST/redirect/GET; no JavaScript is required. Other engines and physical devices remain unverified.

## Additional-service request workflow

Browser execution verified contractor submission, administrator scope review/approval and updated contractor history. Seven page states were inspected at 320/768/1440, including the request form, review queue, administration navigation, pending/recorded review and contractor settings. Two initial settings measurements were inconsistent with the rendered viewport; screenshot-backed rechecks showed no overflow at all three sizes. The raw measurements and rechecks are retained in service-request-layout-checks.json. Internal review notes were absent from contractor views. Firefox/Safari and physical-device execution remain outstanding.

## Lead-alert controls

Contractor preferences, paused/SMS-only states, dashboard/settings navigation and administrator read-only inspection/navigation passed 21 screenshot-backed Chromium checks at 320/768/1440 with no horizontal overflow. Browser execution saved independent choices and confirmed existing offers remained available. Forms work without JavaScript; checkbox accents use navy with native fallback. Additional browser engines and physical devices remain unverified.

## Accepted-lead follow-up

Accepted/overdue/upcoming lists, contractor detail before/after save, dashboard links, administrator request summary and read-only history passed 24 screenshot-backed Chromium checks at 320/768/1440 with no horizontal overflow. Browser execution saved a synthetic estimate/date/note, retained the earlier report and showed follow-up links only on accepted offers. Forms and pagination are server rendered without JavaScript dependence. Other engines and physical devices remain unverified.


## National expansion and prepared multi-engine checks

National home, Minnesota city landing, national operations, private Texas/Florida city previews, state-application queue/review and contractor state request passed 24 Chromium page/width combinations at 320/768/1440 without horizontal overflow or broken local images. The generated restoration scene is labeled illustrative. Additional rewards/location page evidence is recorded in the output report when executed.

Prepared CI config enumerates 56 scenarios across Chromium, branded Chrome/Edge, Firefox, WebKit and Android/iPhone emulation. Tests cover public/private page families at three widths, closed markets/rewards and a no-JavaScript submission/status flow. This configuration has been parsed/listed locally, but those browser-engine runs have not executed. No claim of full Safari, Firefox, Edge or physical-device compatibility is made before their runs pass.
