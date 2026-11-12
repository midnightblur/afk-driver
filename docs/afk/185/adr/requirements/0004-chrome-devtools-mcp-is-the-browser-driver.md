# Setup installs Chrome DevTools MCP as the one browser driver

> Layer: Requirements
> Context ticket: 185

Setup installs one browser driver for Claude and Codex, so that every UI check and every reproduction in a signed-in browser can run. Chrome DevTools MCP passed every live check on this machine, in Chrome and Edge, headless and attached. Edge is not official at Google, but Microsoft documents it.

## Considered Options

- Playwright MCP. Rejected by the developer in i-browser4, because a click after Back failed in every attached run, and attach needs a browser extension.
- No shared driver: each test speaks the browser protocol itself. Rejected in i-browser, because the developer asked for a driver set up once for the plugin and for every repository it serves.
