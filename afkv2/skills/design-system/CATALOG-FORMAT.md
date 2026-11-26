# Catalog format

A design catalog records the look of 1 frontend: its tokens and 1 card per repeating shape. It sits in the catalog folder that the `frontends` entry of the repository config names, and it is committed. Only the design-system skill writes it. `scripts/catalog_files.py check` checks the folder against this page and refuses `bad-catalog` with a list of `problems`.

## Files

| File | Holds |
|------|-------|
| `README.md` | the record of the catalog, by "README" below |
| `tokens.css` | the design tokens as CSS custom properties on `:root`: colours, spacing, radii, type |
| `cards/<shape>.html` | 1 card per shape: an HTML fragment with inline styles that use the tokens of `tokens.css` |

A card holds made-up data only: never a record from a screenshot, the live screen or its database. A card makes no network call: no URL with a scheme and no `//host` address in any place of the card, and no `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`, `import()` or `sendBeacon`. A relative path, a `#id` link and a `data:`, `blob:`, `javascript:`, `mailto:`, `tel:` or `about:` URL pass the check. Inline each asset, and use a `#id` link. `check` refuses `network-call` and `secrets` with the file and the line. `README.md` may name the address and the calls of the live app.

## README

The title line `# Design catalog — <frontend name>`, then these sections, each a `##` heading:

| Section | Holds |
|---------|-------|
| `Scope` | the frontend name, its source folder and the app address used for the screenshots |
| `Cards` | the table below, 1 row per card |
| `Refresh` | how to run `/afkv2:design-system` again for this frontend |

The `Cards` table:

| Column | Holds |
|--------|-------|
| `File` | the card file, relative to the catalog folder, such as `cards/shell.html` |
| `Kind` | `token`, `component`, `shell` or `page` |
| `State` | `checked`: compared side by side with a live screenshot of the shape; `unchecked`: not compared |
| `Screenshot` | the file name of the screenshot a `checked` card was compared with; `—` for an `unchecked` card |

Each card file has 1 row. `tokens.css` needs no row. A file the table does not name is no problem for `check`.

```markdown
| File | Kind | State | Screenshot |
|------|------|-------|------------|
| cards/shell.html | shell | checked | shell.png |
| cards/button.html | component | unchecked | — |
```

The screenshots stay in the afkv2 data folder and are deleted at the end of the run. The names are the record of the comparison.
