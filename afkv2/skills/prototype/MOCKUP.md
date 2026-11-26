# Mockup rules

A mockup is 1 self-contained HTML file per screen in the `prototype/` folder of the spec folder. It looks like the app, and the developer can use it: clicks move between screens, forms check their input, and actions change the in-file state. `prototype_files.py check` enforces the rules of "The file"; the other rules are yours.

## The file

- Inline all CSS and JS. Use no build step, no framework runtime and no import that needs a server.
- The file opens from its `file://` path and makes no network call: no URL with a scheme and no `//host` address in any place of the file, and no `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`, `sendBeacon` or `import()`. A relative path, a `#id` link and a `data:`, `blob:`, `javascript:`, `mailto:`, `tel:` or `about:` URL pass the check. Draw icons as inline SVG, and use the system fonts or the font names of the anchor.
- Never copy the afkv2 tooltip block or any lavish runtime into the file.
- Keep the file near 100 KB, at most 500 KB.

## App shell and neighbours

- Every screen sits inside the app shell: the global navigation, the header and the breadcrumbs of the anchor, with the right navigation item active.
- The mockup is clickable from the entry screen: the developer reaches each new screen by a click from the screen where a story starts, never by a direct open of the new screen.
- Each neighbour screen that the shell or the new screen links to is a stub inside the app shell: its layout, a static content block, and no link deeper than 1 level. A link past the stubs does nothing.

## Behaviour

- Each action of a story works against the in-file data: a row is added, a filter narrows the list, a form shows its errors.
- Show each state that a story implies: empty, loading, error and success, and each permission variant.
- A capability the developer cannot reach by a click is not shown. Build the interaction, not a caption that describes it.

## Made-up data

- In a mockup, every row is made up. Put the rows in 1 JSON script, such as `<script type="application/json" id="data">`, and render each screen from it.
- Use at most 50 rows per screen. Show the density of the app with fewer rows, never with more.
- Invent each name, address, number and date: never a record copied from the live app or its database, also not one seen in a screenshot.
- Write no key, token or password, also no made-up one shaped like a real one: the secret scan of `settle` refuses it.

## Regions

- Put an `id` on every region the developer may note: each table, form, filter bar, card, dialog and navigation block. A lavish note selector stops at the nearest `id`, so a region with an `id` names the element of the note.
- Keep each `id` stable across edits.

## Variants

- When the direction is unclear, put 2 to 3 variants in the 1 file. A `?variant=<name>` parameter picks a variant, and a switcher bar at the edge of the screen changes it.
- Make the variants differ in layout, in the order of the information or in the main action, not only in color.
- At the settle, delete the losing variants and the switcher bar.
