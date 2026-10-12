# Computer-Use Back-Office Agent

Browser automation agent for legacy portals with form handling, uploads, extraction, and CAPTCHA han

**Domain:** Agentic AI
**Language:** python
**Demonstrates:** You ship agents in the messy real world.

## 7-day build plan

- [ ] Day 1: Scaffold the project with a mock browser engine (simulated DOM, form fields, navigation state) that mimics a legacy portal with login, form pages, and file upload endpoints, all driven by in-memory Python objects with no real browser dependency.
- [ ] Day 2: Build the core agent loop with a task queue, action dispatcher, and mock portal session manager that can execute sequential steps (navigate, read field, fill field, click) and log each action with timestamp and result.
- [ ] Day 3: Implement the form-fill module supporting text inputs, dropdowns, checkboxes, and date pickers against the mock portal, with field validation, retry on simulated transient errors, and a structured action receipt for each completed form.
- [ ] Day 4: Add the file-upload and data-extraction modules: the upload handler reads local fixture files and posts them to the mock endpoint, while the extractor scrapes simulated table and confirmation pages into structured JSON output saved to a local results directory.
- [ ] Day 5: Integrate the human-in-the-loop CAPTCHA handler that detects a simulated CAPTCHA challenge in the mock portal response, pauses the agent, prompts the operator via the terminal for the solution, resumes the session with the provided token, and records the interruption in the audit log.
- [ ] Day 6: Add a human confirmation gate for destructive actions (form submit with irreversible flag, bulk upload): the agent prints a diff of pending changes and waits for explicit yes/no input before proceeding, with auto-abort on timeout, and covers all paths with pytest unit and integration tests.
- [ ] Day 7: Package the project as a runnable CLI with argparse (commands: run-task, list-tasks, show-log), add a task-definition YAML schema with example tasks for login, form fill, upload, and extract, wire everything through a config module reading from environment variables with documented placeholders, and ensure the full demo runs end-to-end with a single command.

_A comprehensive README with an architecture diagram is generated on Day 7._
