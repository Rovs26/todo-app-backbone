---
name: "pdf-user-guide-generator"
displayName: "PDF User Guide Generator"
description: "Automatically generate comprehensive PDF user guides for frontend applications by exploring the codebase, launching the app, and capturing screenshots of every page and interactive state using Playwright browser automation."
keywords: ["pdf", "documentation", "user-guide", "screenshots", "playwright", "automation", "frontend", "testing"]
author: "Kiro Power Builder"
---

# PDF User Guide Generator

## Overview

This power generates a complete PDF user guide for any frontend application. It works by scanning the codebase to discover all routes and interactive elements, launching the app locally, using Playwright to navigate every page and trigger every interactive state (modals, tabs, drawers, dropdowns), capturing full-page screenshots, and assembling everything into a structured PDF with a cover page, table of contents, and per-route sections with annotated screenshots.

The power supports React Router, Vue Router, Next.js (pages and app directory), SvelteKit, Nuxt, and any framework with standard routing patterns. It produces a single `user-guide.pdf` file as the final deliverable — never HTML or Markdown.

## Available Steering Files

- **generate-guide** — Complete step-by-step workflow for generating a PDF user guide from any frontend app

Call `readSteering` with `steeringFile="generate-guide.md"` to load the full workflow.

## Available MCP Servers

### Playwright (`playwright`)

Browser automation server used to control a real Chromium browser for navigating pages and capturing screenshots.

**Key tools used:**

- `browser_navigate` — Navigate to a URL
- `browser_snapshot` — Get accessibility snapshot of current page
- `browser_click` — Click interactive elements
- `browser_screenshot` — Capture full-page screenshots
- `browser_wait_for_text` — Wait for content to load

## Workflow Summary

The power follows six strict steps:

1. **Discover all routes** — Scan router configs, Link/NavLink/a elements, router.push/navigate calls, and nav components to build a complete route list with interactive elements per route.

2. **Install dependencies and start the app** — Run `npm install`, install Playwright, start the dev server, and poll until it responds (up to 30s).

3. **Screenshot every page and state** — Navigate each route, wait for load, capture full-page screenshots, trigger interactive elements (modals, tabs, drawers, dropdowns), and capture additional screenshots for each state.

4. **Build a screenshot manifest** — Verify every file exists and compile an absolute-path manifest JSON array.

5. **Generate the PDF** — Use `fpdf2` (Python) to build the PDF from the manifest. Structure: cover page, table of contents, one section per route with screenshots and usage steps.

6. **Verify before finishing** — Confirm all routes have screenshots, PDF exists and is non-empty, and report the absolute path.

## Rules (Strict)

- The final output MUST be a PDF file. Never produce HTML or Markdown as the deliverable.
- Always use absolute file paths when referencing screenshots. Never use relative paths.
- Visit every route in the app. Do not stop at the homepage.
- Capture interactive states (modals, tabs, drawers, dropdowns) — not just static pages.
- Confirm the PDF file exists and is non-empty before finishing.
- Screenshots go in `./user-guide-assets/screenshots/` with descriptive deterministic filenames (no timestamps or random strings).
- Use `fpdf2` for PDF generation. Do NOT use weasyprint, pdfkit, or any HTML-to-PDF tool.

## Best Practices

- Run route discovery BEFORE opening the browser — understand the app structure from source code first.
- Use `networkidle` or `domcontentloaded` + a short delay when navigating to ensure pages are fully rendered.
- Name screenshots descriptively: `page-dashboard.png`, `page-dashboard-modal-add-user.png`.
- Always call `os.path.exists()` on each image before embedding in the PDF — print a warning and skip if missing, never crash.
- Check `vite.config`, `next.config`, or `package.json` for the dev server port; default to 3000.
- Poll the dev server URL for up to 30 seconds before giving up.

## Troubleshooting

### Dev server won't start

**Cause:** Missing dependencies or port conflict.
**Solution:**

1. Run `npm install` first
2. Check if port is already in use: `netstat -ano | findstr :3000`
3. Kill the process or use a different port
4. Check `package.json` scripts for the correct start command

### Playwright not installed

**Cause:** Browser binaries not downloaded.
**Solution:**

1. Run `npm install -D playwright`
2. Run `npx playwright install chromium`
3. Verify with `npx playwright --version`

### Screenshots are blank or incomplete

**Cause:** Page not fully loaded before screenshot.
**Solution:**

1. Increase wait time after navigation
2. Use `browser_wait_for_text` to wait for specific content
3. Check for client-side rendering that needs extra time

### PDF is empty or 0 bytes

**Cause:** No screenshots found or script error.
**Solution:**

1. Check the manifest file for valid absolute paths
2. Verify screenshots exist on disk
3. Run the Python script manually to see error output
4. Ensure `fpdf2` is installed: `pip install fpdf2`

### Routes not discovered

**Cause:** Non-standard routing pattern.
**Solution:**

1. Manually check the router configuration file
2. Look for dynamic routes and API routes
3. Check for route guards or authentication that hides routes
4. Add missing routes to the manifest manually

## Configuration

**No additional configuration required** — the power uses the Playwright MCP server which is configured automatically via the included `mcp.json`.

**Prerequisites:**

- Node.js 16+ (for running the frontend app)
- Python 3.8+ (for PDF generation with fpdf2)
- npm (for dependency installation)

---

**MCP Server:** playwright (`@anthropic-ai/playwright-mcp`)
