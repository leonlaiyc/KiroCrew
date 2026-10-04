# PUBLISH-WAITING — clean zh-TW replacement PR (prepared 2026-10-04)

Branch: leonlaiyc:claude/zh-tw-clean-20261004 @ ab837d457648d19a055d3794412e08b02519eaf2 (one commit on main 4c60e250b)
Compare: https://github.com/kirodotdev/KiroCrew/compare/main...leonlaiyc:claude/zh-tw-clean-20261004
Title: feat(i18n): add Traditional Chinese (Taiwan)

Blocked on (both must be on main first; template allows ≤2 commits, so no stacking):
- #16624 fix(i18n): match the longest do-not-translate term first   (unblocks aws_ssm_session_manager, aws_configure_set)
- #16627 fix(issue-radar): show each provider's own sign-in command (removes the untranslatable auth_login fragment)

STATUS (re-validated 2026-10-04 ~02:50Z): #16624 and #16627 are both still OPEN (Issue Gate red,
WAITING-TRIAGE). Do NOT run anything below until `gh pr view <n> --json state` says MERGED for BOTH.
The body's "Depends on" wording is state-neutral on purpose; it never asserts the merge.

Fast path, once BOTH have merged (worktree kc-wt-claude-zhtw-clean-20261004; claim issue-2571):
 0. Gate: `gh pr view 16624 --json state,mergeCommit` and same for 16627 -> both MERGED, else stop.
 1. git fetch origin main; note NEW=$(git rev-parse origin/main).
 2. Drift inspect (read-only): git log --oneline 4c60e250b..$NEW -- website/src/i18n website/scripts/i18n-*.mjs
    website/scripts/lib website/scripts/check-bundle-size.mjs src/kiro_crew/context.py test/test_context_ui_language.py
    and `git diff 4c60e250b $NEW -- website/src/i18n/locales/en.json website/src/i18n/en.manual.json website/src/i18n/glossary.json`
    (expect at least #16624 passthrough-checks.mjs + #16627 locales/en.json auth_login removal).
 3. git rebase origin/main. Expected overlap: website/scripts/lib/passthrough-checks.mjs (#16624 edits the dnt
    matcher, this branch adds one TARGET_SCRIPTS row: different hunks). Resolve any conflict by keeping both.
 4. Remove apps.issueRadar.views.settings.generalSettings.auth_login from zh-TW.json (#16627 deleted it from every other catalog).
 5. Reconcile every English key added/changed/deleted in en.json / en.manual.json since 4c60e250b (3-way: old-en/new-en/old-zh-TW,
    insert after the zh-CN sibling order), translate added/changed ones to the zh-TW style guide. If the counts change,
    update the "What changed" reconciliation numbers in the body.
 6. Gates (website/): npm run i18n:check (expect all PASS) ; npx vitest run src/i18n/ src/test/IssueRadarSignInCommand.test.tsx
    src/test/passthroughChecks.test.ts (navLabels.test.tsx needs --testTimeout=90000 on this host: timeout-only, not an assertion) ;
    npm run typecheck ; npm run build ; vite build --mode analyze + node scripts/check-bundle-size.mjs (re-measure the zh-TW
    and zh-CN chunk raw/gzip/brotli and update "Manual verification") ; repo root: <venv> -m pytest test/test_context_ui_language.py ;
    BRAND_BASE_REF=origin/main scripts/check_brand_name.py ; git diff --check origin/main...HEAD.
 7. Squash/amend to ONE commit (feat(i18n): add Traditional Chinese (Taiwan)); push --force-with-lease to fork.
 8. Replace HEADSHA in the body with the new head (screenshots are committed blobs under temp-screenshots/i18n-zh-tw/).
 9. Check B: gh pr list --repo kirodotdev/KiroCrew --state open --search "2571" ; claim.py check issue-2571.
10. gh pr create --repo kirodotdev/KiroCrew --head leonlaiyc:claude/zh-tw-clean-20261004 --title "feat(i18n): add Traditional Chinese (Taiwan)" --body-file <body>.
11. Re-fetch live body; diff `^## ` against CURRENT template (Pattern harvest intentionally deleted: feat PR) -> core_headings=OK.
12. Read ONE exact-head review cycle; repair only genuine BLOCK findings, max one substantial round.
13. Only after the replacement PR exists: transfer claim pr-9820, comment on #9820 "Superseded by #<new>, rebuilt from current
    main against the repository's current lazy i18n and translation pipeline." and close #9820.

Proven locally 2026-10-04: zh-TW + #16624 + #16627 (+ step 2) stacked on 4c60e250b -> i18n:check 19 checks PASS; catalogParity, IssueRadarSignInCommand (all 13 languages), passthroughChecks, deadKeys, glossary: 115 passed.

---- BODY BELOW THIS LINE ----

## Problem / Motivation

**Goal:** A dashboard user whose browser asks for Traditional Chinese (Taiwan), or who picks 繁體中文, gets the UI in Taiwan Traditional Chinese instead of Simplified Chinese.

KiroCrew ships no Traditional Chinese catalog. A `zh-TW` browser falls back to `zh-CN` today, so a Taiwanese reader gets Simplified script and Mainland vocabulary (设置, 会话, 文件夹). That's the gap #2571 asks to close.

## Why it matters

Simplified and Traditional are different scripts, and Taiwanese software vocabulary differs from Mainland vocabulary beyond the glyphs (設定 vs 设置, 工作階段 vs 会话, 資料夾 vs 文件夹). Today every Taiwan user reads the whole dashboard in a script and register that isn't theirs. Since #14228, catalogs load lazily, so this catalog costs only the users who choose it.

## Not a goal

- Changing behaviour for any other Chinese tag. `zh`, `zh-Hans`, `zh-Hant`, `zh-HK` and `zh-MO` keep their existing `zh-CN` fallback; a Hong Kong / Macau / generic-Traditional policy is a separate decision.
- A human-translated catalog. This is an AI first pass, held to a written Taiwan style contract, with targeted review.
- Editing any existing locale's translations.
- Generic i18n changes: the do-not-translate matcher (#16624) and Issue Radar's sign-in command (#16627) are their own PRs, which this one builds on.

## What changed (motivation → approach → change)

- **Goal → approach:** add `zh-TW` as catalog #13 through the seams that already exist for a language: the `SUPPORTED_LANGUAGES` registry, the eager `AUTHORED_CATALOGS` map, the lazy `AUTHORED_LOADERS` map, the per-catalog chunk budget, the locale tables the existing gates read, and the backend mirror its drift test requires. No new mechanism.
- **Catalog:** `website/src/i18n/locales/zh-TW.json`, with exact key parity with English (CLDR `other` plural forms only). It's an AI-generated first pass through the repository pipeline (`scripts/i18n-translate.mjs`, `src/i18n/TRANSLATION-PROMPT.md`), held to a new style guide, `src/i18n/style/zh-TW.md`, covering Taiwan terminology, corner-bracket quotes 「」, full-width punctuation, CJK–Latin spacing and 你-register. Settings, authentication, credentials, approvals, destructive confirmations, files, server/instance/tunnel, schedules, sessions/workspace, memory and error/recovery text were reviewed by hand against that guide. **It is not a human translation.**
- **Built from current main, not rebased:** reconciled three-way against the superseded #9820 work (old English source, current English source, old zh-TW). 15,864 translations kept where the English source was unchanged, 0 retranslated (no English source string changed), 38 new keys translated (15 from main @ 59e8b1e22, 22 from #14008, plus `auth_login`, which this branch drops again because #16627 deletes that key), and 0 removed. The result has exactly the current key set, the same key set as `zh-CN.json`.
- **Detection:** `zh-TW` is listed directly after `zh-CN`, so an exact `zh-TW` tag (any case) resolves to it, while every other `zh-*` tag still loose-matches `zh-CN`, the first `zh-*` entry. A stored `zh-TW` choice restores over the browser language.
- **Gates and tables:** `TARGET_SCRIPTS` (passthrough), `OPERAND_QUOTE_PAIRS` (destructive-confirm quoting with 「」), `CATALOG_CHUNK_BUDGETS`, and the backend `_UI_LANGUAGE_CATALOGS`. The authored-catalog ratchet in `catalogParity.test.ts` moves from 12 to 13 now that the lazy seam it waited for exists, and `translateDriver.test.ts` now counts 12 targets. `gh auth login`, `aws configure set` and `/prompts get name` join `glossary.json`'s `dnt`. A new catalog makes every value a changed value, these command literals are untranslatable, and all twelve existing catalogs already keep them verbatim.
- `zhTWStyle.test.ts` enforces the machine-checkable rules: no Simplified-only characters, none of the guide's unambiguous Mainland forms, and corner-bracket quotes only, balanced.
- Docs that count or list the shipped languages now say thirteen and list `zh-TW`.

## Backwards compatibility

Compatible: a language is added. Every existing language, tag resolution and stored choice behaves as before, except that an exact `zh-TW` tag now resolves to its own catalog instead of `zh-CN`, which is the goal. The backend test that used `zh-TW` as its example of a non-catalog tag now uses `zh-HK` and `zh-tw` (still non-restorable, since persisted membership is exact).

Removes nothing: no key, export, rule or ratchet is removed; the ratchet's ceiling rises by one.

## Tests

- `src/i18n/detect.test.ts`: `zh-TW`/`zh-tw` detect as `zh-TW`; preference order holds between the two Chinese catalogs; `zh`, `zh-Hans`, `zh-Hant`, `zh-HK` and `zh-MO` stay on `zh-CN`; a stored `zh-TW` beats a `zh-CN` browser. The pre-existing cases that used `zh-TW` as the "loosely matched" example now use `zh-HK` / `zh-MO`.
- `src/i18n/style/zhTWStyle.test.ts` (new): the style guide's mechanical rules.
- `src/i18n/catalogParity.test.ts` (ratchet 12 → 13) and `src/i18n/translateDriver.test.ts` (11 → 12 targets).
- `test/test_context_ui_language.py`: the drift gate between `_UI_LANGUAGE_CATALOGS` and `SUPPORTED_LANGUAGES` (27 passed).
- Ran locally: `npm run i18n:check` (19 checks PASS against `origin/main`), `npx vitest run src/i18n/` (all files pass; `navLabels.test.tsx`'s lazy `SettingsPage` import needs more than 15 s on this Windows host and passes with `--testTimeout=90000`), `npm run build` (tsc + vite), `vite build --mode analyze` + `node scripts/check-bundle-size.mjs` (846 chunks within budget), ESLint on the changed files, `BRAND_BASE_REF=origin/main scripts/check_brand_name.py`, black/flake8 on the two Python files, `git diff --check`.

## Manual verification

Served the real production build (`website/dist`) with the repository's capture helpers (`scripts/lib/serve-dist.mjs`, `scripts/lib/stub-dashboard-api.mjs`), opened Settings → Display in headless Chromium, and read `document.documentElement.lang` plus the language picker from the DOM:

| build | browser `navigator.languages` | stored `mc-lang` | resolved | picker |
|---|---|---|---|---|
| main 4c60e250b | `zh-TW` | — | `zh-CN` | 自动 — 简体中文 |
| this branch | `zh-TW` | — | `zh-TW` | 自動 — 繁體中文 |
| this branch | `zh-CN` | `zh-TW` | `zh-TW` | 繁體中文 |
| main 4c60e250b | `zh-HK` | — | `zh-CN` | 自动 — 简体中文 |
| this branch | `zh-HK` | — | `zh-CN` | 自动 — 简体中文 (unchanged) |

Measured lazy chunk (`vite build --mode analyze`): `zh-TW` is its own chunk at 995,837 B raw / 348,394 B gzip / 281,260 B brotli (`zh-CN` for comparison: 956,090 / 342,996 / 279,009), against the shared 3 MB per-catalog budget. zh-TW catalog strings appear only in that chunk; the first-load chunks gain only the `繁體中文` picker label.

## Screenshots / video

1. main, `zh-TW` browser → existing fallback to Simplified:

![main: zh-TW browser falls back to zh-CN](https://github.com/kirodotdev/KiroCrew/raw/HEADSHA/temp-screenshots/i18n-zh-tw/before-browser-zh-TW.png)

2. this branch, `zh-TW` browser → 繁體中文:

![branch: zh-TW browser gets 繁體中文](https://github.com/kirodotdev/KiroCrew/raw/HEADSHA/temp-screenshots/i18n-zh-tw/after-browser-zh-TW.png)

3. this branch, stored `zh-TW` overrides a `zh-CN` browser:

![branch: stored zh-TW overrides zh-CN browser](https://github.com/kirodotdev/KiroCrew/raw/HEADSHA/temp-screenshots/i18n-zh-tw/after-stored-zh-TW-over-zh-CN.png)

4. `zh-HK` is unchanged (main, then this branch):

![main: zh-HK resolves to zh-CN](https://github.com/kirodotdev/KiroCrew/raw/HEADSHA/temp-screenshots/i18n-zh-tw/before-browser-zh-HK.png)
![branch: zh-HK still resolves to zh-CN](https://github.com/kirodotdev/KiroCrew/raw/HEADSHA/temp-screenshots/i18n-zh-tw/after-browser-zh-HK.png)

Files committed under `temp-screenshots/i18n-zh-tw/` (fork PR: `--attach` is unavailable).

## Related Issues

Fixes #2571
Supersedes #9820. This is a fresh current-main implementation against the repository's lazy i18n and translation pipeline, not a rebase of it.
Depends on #16624 and #16627.

## Checklist

- [x] At most two commits (one is the norm), with a Conventional Commits title (`feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert: ...`)
- [x] Existing tests pass and new tests added for new functionality
- [x] Self-review completed; code follows project style guidelines
- [x] Documentation updated (if applicable)
- [x] No secrets, credentials, or internal references in the diff

## Contribution License Agreement

<!-- PLACEHOLDER: The exact CLA wording will be supplied by OSPO before the first public PR.
     Do not invent CLA text — it will be added here once Legal provides it. -->

🤖 Generated with [Claude Code](https://claude.com/claude-code)
