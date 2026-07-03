# Contributing to Qortium

Thanks for helping improve Qortium. This repository is part of the public
Qortium Work Log, so issues and pull requests should leave a clear trail for
maintainers and future contributors.

## Work Log

The public work board lives at:

<https://github.com/orgs/QortiumDev/projects/1>

Use the board to see active work, but treat GitHub issues as the source of truth
for discussion and pull request links. Maintainers handle official assignment,
priority, review, and merge decisions.

## Choosing Work

- Look for issues labeled `good first issue` or `help wanted`.
- Comment before starting if an issue needs clarification or if you want to
  request assignment.
- Wait for maintainer direction on issues labeled `needs discussion` or
  `needs maintainer approval`.
- If an issue is labeled `claimed` or `in progress`, coordinate in the issue
  before opening a competing pull request.

## Contribution Flow

1. Find or open an issue that describes the change.
2. Comment with the approach you plan to take, especially for behavior, content,
   or policy changes.
3. Create a focused branch and keep the pull request scoped to the issue.
4. Link the issue in the pull request body with `Refs #123` or `Fixes #123`
   when appropriate.
5. Include the checks you ran, such as `npm run check` or `npm run build`.
6. Respond to maintainer review and keep discussion on the issue or pull
   request so the Work Log remains useful.

## Labels and Statuses

| Label or status | Meaning |
| --- | --- |
| `worklog` | Tracked in the public Qortium Work Log. |
| `help wanted` | Maintainers welcome contributor help. |
| `good first issue` | Suitable for a smaller, lower-context contribution. |
| `needs discussion` | The approach or policy needs agreement before work starts. |
| `claimed` | Someone has asked to take the issue; confirm before duplicating work. |
| `in progress` | Work is actively underway. |
| `needs maintainer approval` | A maintainer decision is required before the change can move forward. |

## Local Checks

Install dependencies once:

```sh
npm install
```

Useful checks before opening a pull request:

```sh
npm run check
npm run build
```

For content-only changes, still run the most relevant check you can and note any
checks you skipped in the pull request.
