# Evaluation plan

## Development verification — 23 September 2026

- Django configuration check: passed.
- Backend tests: 11 passed on SQLite, including the complete lending cycle and CSRF protection.
- Vite production build: passed.
- Browser checks: catalogue loaded 108 records; accession search returned the expected book; staff login succeeded; wrong-shelf verification showed the correct destination; a subsequent correct scan made the returned book available.
- Camera hardware, participant usability testing, production deployment and PostgreSQL concurrency have not been verified.

Deployment preparation: the expanded 16-test suite passes locally, covering proxy-origin CSRF, secure cookies, account-wide login lockout despite changing client headers, health/cache headers and one-time staff bootstrap. Production settings checks pass with two documented policy exceptions: username-based Axes protection behind shared proxies and no browser HSTS preload submission for provider-owned demo domains. Vercel configuration type-checks and the frontend production build passes. Hosted PostgreSQL checks are configured in GitHub Actions; their result must be verified after pushing.

## Functional acceptance

| ID | Task | Expected result |
| --- | --- | --- |
| T-01 | Search by title, author, ISBN, category and accession | Correct Book records, availability and floor/section/shelf location |
| T-02 | Change a shelf code in admin, browse the map and scan the original QR | Updated location appears; old QR still identifies the same shelf |
| T-03 | Check out an available Book, attempt checkout again | First loan succeeds; duplicate is rejected |
| T-04 | Return a Book, scan the wrong shelf, then the right shelf | Awaiting shelving → misplaced alert → available; both scans are logged |
| T-05 | Compare yesterday/today/tomorrow due dates and record a return | Only unreturned loans due before today are overdue; return removes the loan from the active list |
| T-06 | Access staff endpoints anonymously or as a nonstaff user | Requests denied; public search and map remain accessible |
| T-07 | Log a reminder for an overdue loan | Audit record created; UI clearly states no message was sent |
| T-08 | Deny camera permission, then enter printed codes | Clear camera fallback; manual verification still works |
| T-09 | Scan a borrowed Book, submit malformed/unknown codes | Clear error; no shelving state or loan is altered |

## Usability study (not yet performed)

Recruit five representative students and two staff participants with consent. Give each student a title to find and ask them to identify the floor, section and shelf. Ask staff to check out, return and correctly shelve a Book, including one deliberate mismatch. Record completion without help, elapsed time, incorrect actions and comments. Collect a 1–5 ease rating after each task. Suggested acceptance: at least 80% unassisted completion and median ease rating ≥4. Do not present simulated data as participant results.

## Performance (not yet measured)

Use the same machine, documented Python/Node versions, database and seed size for every run. Warm the API once, then measure 100 sequential catalogue searches and shelf-map reads; report median/p95 latency and errors. Suggested local-demo target: p95 under 500 ms with zero errors for 108 books. Test a larger fixture before claiming scalability. Separately run concurrent checkout attempts on PostgreSQL and confirm exactly one active loan per Book. Record real measurements, hardware and method here once performed; passing unit tests does not establish latency or usability.
