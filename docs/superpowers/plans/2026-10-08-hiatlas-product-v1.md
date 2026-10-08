# HiAtlas product v1 integration plan

Goal: create a local integration branch rooted at validated Data Hub 02ae9b3, preserving Foundation and Data Hub.
Architecture: selectively import local gate infrastructure from 97f527b and backend context role metadata from the Foundation-relative customer bridge. Adapt the authenticated customer flow to the existing real Data Hub workspace, without importing the demo catalog.
Constraints: no main base/change, merge, deployment, public Demo change, push, branch deletion or BUG-03B implementation.

- [x] Verify official remote, exact source commits and isolated integration branch.
- [x] Audit 641e575..00e585e and distinguish bridge changes from release-only behavior.
- [x] Integrate the ten gate infrastructure files, preserving the Data Hub test harness and dependencies.
- [x] Pin customer login/context/unknown-profile regressions with failing tests, then adapt the bridge.
- [x] Review final diff for demo leakage, run official complete gate with zero skips and cleanup.
- [x] Record validation and commit locally on integration/hiatlas-product-v1.

Review focus: session revalidation; unknown or missing roles; object prototype role names; permission-controlled Data Hub; context switching and revocation. Existing context/provider tests plus added customer tests cover these boundaries. No local profile grants capabilities.
Full validation also required reviewed editor readiness and native shutdown amendments, described in the product integration audit.
