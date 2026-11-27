# Mockup rules

A mockup is 1 self-contained HTML file in the `prototype/` folder of the spec folder, and it holds every screen. It looks like the app, and the developer can use it: clicks move between screens, forms check their input, and actions change the in-file state. `prototype_files.py check` enforces the rules of "The file" and "Screens and routes"; the other rules are yours.

## The file

- Inline all CSS and JS. Use no build step, no framework runtime and no import that needs a server.
- The file opens from its `file://` path and makes no network call: no URL with a scheme and no `//host` address in any place of the file, and no `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`, `sendBeacon` or `import()`. A relative path, a `#id` link and a `data:`, `blob:`, `javascript:`, `mailto:`, `tel:` or `about:` URL pass the check. Draw icons as inline SVG, and use the system fonts or the font names of the anchor.
- Never copy the afkv2 tooltip block or any lavish runtime into the file.
- Keep the file near 100 KB per screen, at most 500 KB.

## Screens and routes

lavish annotates only the file that it opened, and it refuses a load of that file with a changed query. So the mockup never loads a page: every click stays in the 1 file.

- Route each screen by the hash: `#/<screen>`, with its parameters after it, such as `#/detail?id=7&as=ann`. Render the screen on load and on `hashchange`.
- Keep all state in the hash or in the in-file data, also the viewer and the variant. Never read or write `location.search` or `location.pathname`.
- Link only to a `#` route. Never link to another file, never call `location.assign`, `location.replace` or `location.reload`, and never let a form submit: handle it in script.
- lavish drops the hash when it reloads the file after an edit. Keep the route in `window.name` at each render, such as `mockup:#/detail?id=7`, and restore it on load when the hash is empty. An unknown route shows the entry screen.

## App shell and neighbours

- Every screen sits inside the app shell: the global navigation, the header and the breadcrumbs of the anchor, with the right navigation item active.
- The mockup is clickable from the entry screen: the developer reaches each new screen by a click from the screen where a story starts, never by a direct open of the new screen.
- Each neighbour screen that the shell or the new screen links to is a stub inside the app shell: its layout, a static content block, and no link deeper than 1 level. A link past the stubs does nothing.

## Components of the anchor

The standard components of the app change over time, so their look is read at run time from the anchor, never from a rule in this skill.

- Draw each table, list, form field, dialog, button, tab and status mark from the component of the anchor for that shape: its catalog card, else the source component that step 2 read. Copy it with every part of it, such as the filter row and the sticky header of a table, its row style and its footer with paging, and with its sizes, type and colours.
- Never draw your own variant of a shape that the anchor has a component for. A different part is a decision: the developer asks for it, or the PRD needs it. Record it in the Decisions section, with why.
- A shape that the anchor has no component for: build it from the tokens of the anchor, and name it in the Decisions section.

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
- Start each `id` with its screen, such as `detail-items`: the note names no route, so the `id` names the screen.
- Keep each `id` stable across edits.

## Variants

- When the direction is unclear, put 2 to 3 variants in the 1 file. A `variant=<name>` parameter of the hash route picks a variant, and a switcher bar at the edge of the screen changes it.
- Make the variants differ in layout, in the order of the information or in the main action, not only in color.
- At the settle, delete the losing variants and the switcher bar.
