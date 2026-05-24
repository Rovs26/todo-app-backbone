# Generate PDF User Guide — Complete Workflow

This steering file provides the full step-by-step instructions for generating a PDF user guide from a frontend application.

---

## Prerequisites

Before starting, ensure:
- The frontend project is in the current workspace
- Node.js 16+ is installed
- Python 3.8+ is installed
- npm is available

---

## Step 1: Discover All Routes

**Goal:** Build a complete route list and note interactive elements per route BEFORE opening a browser.

### 1.1 Identify the Framework

Scan the project to determine the frontend framework and routing approach:

| Framework | Router Config Location |
|-----------|----------------------|
| React (react-router) | `src/App.tsx`, `src/routes.tsx`, `src/router/index.tsx` |
| Vue (vue-router) | `src/router/index.ts`, `src/router/index.js` |
| Next.js (pages) | `pages/` directory structure |
| Next.js (app dir) | `app/` directory structure |
| SvelteKit | `src/routes/` directory structure |
| Nuxt | `pages/` directory structure |

### 1.2 Extract Routes

Search for ALL of the following patterns across the codebase:

```
- Router config files (Route definitions, path properties)
- <Link to="...">, <NavLink to="...">, <a href="...">
- router.push(...), navigate(...), useNavigate()
- Sidebar/nav components listing pages
- Dynamic route parameters (e.g., /users/:id → use a sample ID)
```

### 1.3 Identify Interactive Elements Per Route

For each route, scan the component source code for:

```
- Modals: Dialog, Modal, Drawer components or aria-modal attributes
- Tabs: Tab, TabPanel, TabList components
- Drawers: Drawer, Sidebar toggle components
- Dropdowns: Select, Dropdown, Menu, Popover components
- Accordions: Accordion, Collapse, Expandable components
- Forms: Form submissions, multi-step wizards
- Tooltips: Tooltip components (hover states)
```

### 1.4 Build the Route Map

Create a structured list:

```json
[
  {
    "route": "/",
    "label": "Home",
    "component": "src/pages/Home.tsx",
    "interactiveElements": []
  },
  {
    "route": "/dashboard",
    "label": "Dashboard",
    "component": "src/pages/Dashboard.tsx",
    "interactiveElements": [
      {"type": "modal", "trigger": "Add User button", "name": "add-user"},
      {"type": "tab", "trigger": "Analytics tab", "name": "analytics-tab"}
    ]
  }
]
```

**Important:** Do NOT skip any route. Every route must be visited.

---

## Step 2: Install Dependencies and Start the App

### 2.1 Install Project Dependencies

```bash
npm install
```

### 2.2 Install Playwright

```bash
npm install -D playwright
npx playwright install chromium
```

### 2.3 Determine the Dev Server Port

Check these files in order for port configuration:
1. `vite.config.ts` / `vite.config.js` — look for `server.port`
2. `next.config.js` / `next.config.mjs` — look for port in dev script
3. `package.json` — look for `--port` flag in `dev` or `start` script
4. Default to port `3000` if not found

### 2.4 Start the Dev Server

```bash
npm run dev &
```

Or the appropriate start command from `package.json` scripts.

### 2.5 Poll Until Server Responds

Poll `http://localhost:<port>` every 2 seconds for up to 30 seconds. If the server does not respond within 30 seconds, check for errors and retry.

```bash
# Example polling (adapt to actual implementation)
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 && break
  sleep 2
done
```

---

## Step 3: Screenshot Every Page and State

**Use the Playwright MCP server to control a real Chromium browser.**

### 3.1 Create Screenshots Directory

```bash
mkdir -p ./user-guide-assets/screenshots
```

### 3.2 For Each Route

For every route in the route map:

1. **Navigate** to `http://localhost:<port><route>`
2. **Wait** for `networkidle` or `domcontentloaded` + 2 second delay
3. **Take a full-page screenshot** saved to `./user-guide-assets/screenshots/page-<route-slug>.png`
   - Route slug: replace `/` with `-`, remove leading dash. Examples:
     - `/` → `page-home.png`
     - `/dashboard` → `page-dashboard.png`
     - `/settings/profile` → `page-settings-profile.png`
4. **Log the absolute path** of the screenshot

### 3.3 For Each Interactive Element

For every interactive element identified in Step 1:

1. **Click/trigger** the element (button, tab, link that opens modal/drawer)
2. **Wait** for the state change (animation complete, content visible)
3. **Take a screenshot** with descriptive suffix:
   - `page-dashboard-modal-add-user.png`
   - `page-dashboard-tab-analytics.png`
   - `page-settings-drawer-notifications.png`
4. **Close/reset** the interactive state (close modal, etc.) before moving to next element
5. **Log the absolute path** of each screenshot

### 3.4 Screenshot Naming Convention

```
page-<route-slug>.png                          — Base page screenshot
page-<route-slug>-<element-type>-<name>.png    — Interactive state screenshot
```

**Rules:**
- All lowercase
- Hyphens as separators
- No timestamps or random strings
- Descriptive and deterministic

---

## Step 4: Build a Screenshot Manifest

### 4.1 Verify All Files Exist

For every screenshot path logged in Step 3, verify the file exists on disk using absolute paths.

### 4.2 Compile the Manifest

Build a JSON manifest with this structure:

```json
[
  {
    "route": "/",
    "label": "Home",
    "screenshots": [
      "C:/absolute/path/to/user-guide-assets/screenshots/page-home.png"
    ]
  },
  {
    "route": "/dashboard",
    "label": "Dashboard",
    "screenshots": [
      "C:/absolute/path/to/user-guide-assets/screenshots/page-dashboard.png",
      "C:/absolute/path/to/user-guide-assets/screenshots/page-dashboard-modal-add-user.png",
      "C:/absolute/path/to/user-guide-assets/screenshots/page-dashboard-tab-analytics.png"
    ]
  }
]
```

**Critical:** All paths MUST be absolute. Never use relative paths.

### 4.3 Validate Completeness

Check that:
- Every route from Step 1 has at least one screenshot
- Every interactive element has its own screenshot
- No paths point to missing files

If any are missing, go back to Step 3 and capture the missing screenshots.

---

## Step 5: Generate the PDF

### 5.1 Install fpdf2

```bash
pip install fpdf2
```

**Important:** Do NOT use weasyprint, pdfkit, or any HTML-to-PDF tool. Only fpdf2 is allowed.

### 5.2 Write the PDF Generation Script

Create a Python script (`generate_pdf.py`) that:

1. **Loads the manifest** (the JSON from Step 4)
2. **For each image, calls `os.path.exists()`** before embedding:
   - If missing: print a warning and skip (do NOT crash)
   - If present: embed in the PDF
3. **Structures the PDF as:**

#### Cover Page
- Application name (from package.json or project directory name)
- "User Guide"
- Generation date

#### Table of Contents
- List of all routes/sections with page numbers

#### One Section Per Route
- Section heading (route label)
- Full-page screenshot(s) with captions
- Screenshots of interactive states with captions
- Numbered step-by-step usage guide inferred from the UI elements and source code

### 5.3 Run the Script

```bash
python generate_pdf.py
```

The script must save to `./user-guide.pdf` and print its absolute path.

### 5.4 Handle Failures

If the PDF file is missing or 0 bytes after running:
1. Check Python script output for errors
2. Verify fpdf2 is installed correctly
3. Check that at least one screenshot exists and is valid
4. Debug and retry

---

## Step 6: Verify Before Finishing

### 6.1 Verification Checklist

Confirm ALL of the following:

- [ ] Every discovered route has at least one screenshot
- [ ] Every interactive state has a screenshot
- [ ] `./user-guide.pdf` exists
- [ ] `./user-guide.pdf` is non-empty (file size > 0 bytes)
- [ ] PDF sections contain embedded screenshots (not broken placeholders)

### 6.2 Final Report

Report to the user:
1. **Absolute path** to `user-guide.pdf`
2. **List of all pages documented** (route → screenshot count)
3. **Any warnings** (missing screenshots, skipped elements)

### 6.3 If Verification Fails

- If routes are missing screenshots → go back to Step 3
- If PDF is empty → go back to Step 5 and debug
- If interactive states are missing → go back to Step 3.3
- Never report success if verification fails

---

## Example Output Structure

```
project-root/
├── user-guide-assets/
│   └── screenshots/
│       ├── page-home.png
│       ├── page-dashboard.png
│       ├── page-dashboard-modal-add-user.png
│       ├── page-dashboard-tab-analytics.png
│       ├── page-settings.png
│       ├── page-settings-drawer-notifications.png
│       └── page-login.png
├── generate_pdf.py
├── screenshot-manifest.json
└── user-guide.pdf
```

---

## Framework-Specific Route Discovery Tips

### React Router (v6)
```javascript
// Look for createBrowserRouter or <Route> elements
const router = createBrowserRouter([
  { path: "/", element: <Home /> },
  { path: "/dashboard", element: <Dashboard /> },
]);
```

### Next.js (App Directory)
```
app/
├── page.tsx          → /
├── dashboard/
│   └── page.tsx      → /dashboard
├── settings/
│   └── page.tsx      → /settings
```

### Next.js (Pages Directory)
```
pages/
├── index.tsx         → /
├── dashboard.tsx     → /dashboard
├── settings/
│   └── index.tsx     → /settings
```

### Vue Router
```javascript
// Look for routes array in router/index.ts
const routes = [
  { path: '/', component: Home },
  { path: '/dashboard', component: Dashboard },
];
```

### SvelteKit
```
src/routes/
├── +page.svelte      → /
├── dashboard/
│   └── +page.svelte  → /dashboard
```

### Nuxt
```
pages/
├── index.vue         → /
├── dashboard.vue     → /dashboard
```

---

## PDF Generation Script Template

```python
import json
import os
from datetime import date
from fpdf import FPDF

class UserGuidePDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.cell(0, 10, "User Guide", align="R", new_x="LMARGIN", new_y="NEXT")
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

def generate_user_guide(manifest_path, output_path, app_name="Application"):
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    pdf = UserGuidePDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Cover Page
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 32)
    pdf.ln(60)
    pdf.cell(0, 20, app_name, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 24)
    pdf.cell(0, 15, "User Guide", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 14)
    pdf.ln(10)
    pdf.cell(0, 10, f"Generated: {date.today().isoformat()}", align="C", new_x="LMARGIN", new_y="NEXT")

    # Table of Contents
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 15, "Table of Contents", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 12)
    for i, entry in enumerate(manifest, 1):
        pdf.cell(0, 8, f"{i}. {entry['label']} ({entry['route']})", new_x="LMARGIN", new_y="NEXT")

    # Sections
    for entry in manifest:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 12, f"{entry['label']}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "I", 11)
        pdf.cell(0, 8, f"Route: {entry['route']}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        for screenshot_path in entry.get("screenshots", []):
            if not os.path.exists(screenshot_path):
                print(f"WARNING: Screenshot not found, skipping: {screenshot_path}")
                continue

            # Add screenshot
            pdf.set_font("Helvetica", "", 10)
            caption = os.path.basename(screenshot_path).replace(".png", "").replace("-", " ").title()
            pdf.cell(0, 6, caption, new_x="LMARGIN", new_y="NEXT")

            try:
                page_width = pdf.w - pdf.l_margin - pdf.r_margin
                pdf.image(screenshot_path, x=pdf.l_margin, w=page_width)
                pdf.ln(5)
            except Exception as e:
                print(f"WARNING: Could not embed image {screenshot_path}: {e}")

        # Usage steps
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Usage Steps:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, f"1. Navigate to {entry['route']}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 7, "2. Review the page content displayed above", new_x="LMARGIN", new_y="NEXT")
        if len(entry.get("screenshots", [])) > 1:
            pdf.cell(0, 7, "3. Interact with available controls (see screenshots above)", new_x="LMARGIN", new_y="NEXT")

    # Save
    pdf.output(output_path)
    abs_path = os.path.abspath(output_path)
    file_size = os.path.getsize(abs_path)
    print(f"PDF generated: {abs_path} ({file_size} bytes)")
    if file_size == 0:
        raise RuntimeError("PDF file is empty!")
    return abs_path

if __name__ == "__main__":
    generate_user_guide("screenshot-manifest.json", "user-guide.pdf")
```

---

## Key Reminders

1. **Always absolute paths** — Every screenshot reference must use the full absolute path.
2. **Never skip routes** — Every route discovered in Step 1 must be visited and screenshotted.
3. **Interactive states matter** — Modals, tabs, drawers, dropdowns all need their own screenshots.
4. **fpdf2 only** — No weasyprint, pdfkit, or HTML-to-PDF tools.
5. **Verify before reporting** — Never claim success without confirming the PDF exists and is non-empty.
6. **Deterministic filenames** — No timestamps, UUIDs, or random strings in screenshot names.
