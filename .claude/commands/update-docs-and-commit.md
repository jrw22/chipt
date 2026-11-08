---
description: Update project docs to reflect the current changes, then commit on a feature branch
argument-hint: "[optional: summary or intent of the change]"
allowed-tools: Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git checkout -b:*), Bash(git switch -c:*), Bash(git add:*), Bash(git commit:*), Bash(git rev-parse:*), Read, Edit, Write, Glob, Grep
---

# Update docs and commit

Make sure the project documentation reflects the pending changes, then commit code and docs together, following the Repository Etiquette in `CLAUDE.md`.

User-provided context for this change (may be empty): $ARGUMENTS

## Current state

- Branch: !`git branch --show-current`
- Status: !`git status --short`
- Recent commits: !`git log --oneline -10 2>/dev/null || echo "No commits yet"`

## Steps

### 1. Understand the change
- If there are no changes (empty status), say so and stop.
- Review what changed. Run `git diff` and `git diff --cached`, and read any new untracked files.
- Summarise the change in one or two sentences. If `$ARGUMENTS` was given, use it as the stated intent.
- If the changes cover several unrelated things, plan **separate focused commits**, one per logical change. Don't lump them into one commit.

### 2. Make sure you're on a feature branch
- **Never commit directly to `main`.**
- If the current branch is `main` (or `master`), create a branch first: `git checkout -b feature/<short-description>`, or `fix/<short-description>` for bug fixes. Use lowercase, hyphen-separated names that describe the change.
- If you're already on a `feature/` or `fix/` branch, stay on it.

### 3. Update the docs
Update only the docs the change actually affects. Keep edits concise and factual, and don't invent plans or details that aren't in the code, `project_spec.md`, or the user's context.

| File | Update when… | How |
|---|---|---|
| `docs/changelog.md` | Always, for any user-visible, functional, or structural change | Follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Add entries under an `## [Unreleased]` section (create it below the intro if missing) using the `### Added` / `### Changed` / `### Fixed` / `### Removed` subsections. |
| `docs/project_status.md` | Progress was made toward a milestone, or something got blocked | Keep these sections (create them if the file is empty): **Current milestone**, **Done**, **In progress**, **Next up**, **Blockers / open questions**. Tick off MVP items from `project_spec.md` §3 as they're completed. |
| `docs/architecture.md` | New components, modules, data flows, API endpoints, or DB schema changes | Fill in the relevant existing section (System Overview, Data Flow, Component Architecture). |
| `CLAUDE.md` | The repo structure, tech stack, conventions, or testing checklist changed | Update the Architecture Overview tree and any affected sections. |
| `project_spec.md` | A design decision was made or changed, or an open question was resolved | Update the relevant section and the §7 decisions log. |
| `.env.example` | A new config/env variable was introduced or one was removed | Add it with a placeholder value and a short comment, in the matching section. |

### 4. Safety checks before staging
- **Never stage `.env`** or any other file with real secrets, credentials, or API keys. If you see one in the diff, stop and warn the user.
- Don't stage scraper cache output (`.cache/`) or other files covered by `.gitignore`.
- Stage files explicitly by path (`git add <paths>`). Don't use `git add -A` or `git add .`.

### 5. Commit
- Commit the code change **and** its doc updates together in the same commit.
- Write a clear commit message:
  - A subject line under ~72 characters in the imperative mood (e.g. "Add resultsbase scraper").
  - A blank line, then a short body explaining *what* changed and *why*. Mention which docs were updated.
- If you planned multiple focused commits in step 1, repeat steps 3–5 for each.

### 6. Report back
- Show the branch name, the commit hash(es) and subject(s), and the list of docs updated.
- **Don't push or open a PR** unless the user asks. Remind them of the next steps from `CLAUDE.md`: test locally, then `git push -u origin <branch>` and open a PR into `main`.
