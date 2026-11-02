# Service landing-page completion

## Current scope

This continuation starts from development merge `01b685b6d5edefdd7f6b2409db1b84bc44f91b46` (PR #2). GitHub Actions run [41383800865](https://github.com/alamotte1956/best-leads-mn/actions/runs/41383800865) passed for that merge. That result does not cover this continuation until it is published and checked separately.

The continuation adds five service pages per state, thirty routes in total, with local illustrative photographs, the approved USA logo, state and initial-market information, service scope guidance and navigation. It also enriches the ten retained Minnesota service pages with geographic information, request guidance, fixed-origin metadata, social previews and WebPage JSON-LD, and adds a Minnesota sitemap. No business address, reviews, prices, response guarantees or insurance-coverage promises are invented.

## Exact primary Minnesota URLs

These routes already exist in the merged GitHub development branch. Their richer content and metadata are part of this continuation. The production version has not been verified in this session.

| Service | URL |
| --- | --- |
| Water | https://RestorationContractorsMN.com/services/water-damage |
| Fire and smoke | https://RestorationContractorsMN.com/services/fire-smoke-damage |
| Mold | https://RestorationContractorsMN.com/services/mold-remediation |
| Storm and hail | https://RestorationContractorsMN.com/services/storm-hail-damage |
| Roofing repair | https://RestorationContractorsMN.com/services/roof-repair |

## New national service URLs

Each base below has five exact service suffixes: `water-damage`, `fire-smoke-damage`, `mold-remediation`, `storm-hail-damage`, `roof-repair`.

| State | Base URL | Current route behavior |
| --- | --- | --- |
| Minnesota | https://RestorationContractorsUSA.com/usa/minnesota/services/ | Public in this continuation; links to retained Minnesota service request forms |
| Texas | https://RestorationContractorsUSA.com/usa/texas/services/ | Public 404; authenticated preview only |
| Florida | https://RestorationContractorsUSA.com/usa/florida/services/ | Public 404; authenticated preview only |
| North Carolina | https://RestorationContractorsUSA.com/usa/north-carolina/services/ | Public 404; authenticated preview only |
| Georgia | https://RestorationContractorsUSA.com/usa/georgia/services/ | Public 404; authenticated preview only |
| Wisconsin | https://RestorationContractorsUSA.com/usa/wisconsin/services/ | Public 404; authenticated preview only |

For example, the Texas roof preview route is `/admin/national/preview/texas/services/roof-repair`. Every preview requires a current administrator session, returns no-store, is noindex, has no canonical/structured-data publication signal, and offers no intake form for a closed market. Preview service links stay in the private preview family. State pages link to their service pages/previews.

`/sitemap.xml` on Minnesota lists the homepage and ten existing service URLs. On the exact USA hostname it redirects to `/usa/sitemap.xml`. The national sitemap includes service routes only for enabled states. Canonicals and sitemap locations do not trust arbitrary Host headers.

## Verification boundaries

Automated coverage checks all ten Minnesota pages, native request submission for every service, all thirty national service routes and administrator previews, available local photos, and sitemap/launch/authentication boundaries. The full suite passed 241 tests and all three JavaScript fallback checks passed. The additional Windows WebP platform-mapping regression then passed with the four-test photo suite. Providers remain disabled during tests. Rendered browser verification for these new pages and a new remote CI run are still required after publishing. No deployment or production schema change is included.

## Consumer/contractor reset

Completed November 2, 2026 after final explicit owner confirmation. All 8 contractor records, 12 homeowner leads and related records were removed from the live Best Leads 2 database. All 12 selected customer tables were verified empty; all 14 public tables remained. Administrator configuration and business-expense data were preserved. Recovery snapshot and restore-tested private archive retained. Website health returned status ok. See DATA_RESET.md for scope and verification. No website code deployment was performed.

## Advantages messaging and browser coverage follow-up

The Minnesota home, contractor registration, national/state home and both service templates now share an advantages section. It emphasizes restoration focus, property ZIP/service/approved-coverage matching, credential-evidence review, private request tracking and contractor offer choice. No comparative savings, guaranteed availability, guaranteed outcomes or exclusive-lead marketing claim is added. The approved branding and responsive color scheme are retained.

Validation: all 242 Python tests and three JavaScript fallback checks passed. Browser test discovery and JavaScript syntax checks passed for 105 scenarios across seven projects. The expanded matrix adds all thirty private state-service previews at three widths, includes the five public Minnesota national service routes, checks all five closed-state service families and exercises the roofing request form without JavaScript. These new browser scenarios have been prepared and enumerated, not executed locally or remotely yet. They require publishing and a fresh CI run; the previous green CI run does not establish their result.
