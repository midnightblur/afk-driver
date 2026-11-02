/* An unsent note is an element with the attribute contract of the send runtime. It adds the lines
 * `<element id> <mark or em dash> | <note>`, `<note id> edit | <text>` and `<note id> delete`. */
(function () {
  var bar = document.getElementById('afkv2-send');
  var form = document.getElementById('afkv2-answer-form');
  if (!bar || !form) return;
  var round = bar.getAttribute('data-afkv2-round');
  var KEY = 'afkv2-draft:' + bar.getAttribute('data-afkv2-session') + ':' + round + ':notes';
  var EDIT = 'edit', DELETE = 'delete';
  var SETTLED_MARKS = {
    decided: [['accept', 'Accept'], ['reopen', 'Reopen']],
    confirm: [['accept', 'Accept'], ['reopen', 'Reopen']],
    signoff: [['sign', 'Sign'], ['reopen', 'Reopen']],
    debate: [['reopen', 'Reopen']]
  };

  function make(tag, className, text) {
    var el = document.createElement(tag);
    if (className) el.className = className;
    if (text) el.textContent = text;
    return el;
  }

  var panel = make('div', 'afkv2-note-drafts');
  panel.id = 'afkv2-note-drafts';
  panel.hidden = true;
  panel.appendChild(make('h3', '', 'Your unsent notes'));
  bar.parentNode.insertBefore(panel, bar);

  /* Same two stores as the runtime, for the same reason: a sandboxed frame may
   * refuse `localStorage`, and `window.name` survives the reload of a re-render. */
  function readStore() {
    try {
      var drafts = (JSON.parse(window.name || '{}') || {}).afkv2Answers;
      if (drafts && drafts[KEY]) return drafts[KEY];
    } catch (e) {}
    try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { return {}; }
  }

  function writeFrame(value) {
    try {
      var envelope = {};
      try { envelope = JSON.parse(window.name || '{}') || {}; } catch (e) {}
      if (!envelope.afkv2Answers) envelope.afkv2Answers = {};
      if (value) envelope.afkv2Answers[KEY] = value; else delete envelope.afkv2Answers[KEY];
      window.name = JSON.stringify(envelope);
    } catch (e) {}
  }

  function entries() { return [].slice.call(panel.querySelectorAll('.afkv2-note-draft')); }

  function fieldOf(entry) { return entry.querySelector('textarea'); }

  function markOf(entry) {
    var picked = entry.querySelector('input[type="radio"]:checked');
    return picked ? picked.value : '';
  }

  function save() {
    var drafts = {};
    entries().forEach(function (entry) {
      var field = fieldOf(entry), mark = markOf(entry), text = field ? field.value : '';
      if (mark || text) drafts[entry.getAttribute('data-afkv2-item')] = { c: mark, n: text, a: entry.getAttribute('data-afkv2-note-action') };
    });
    writeFrame(drafts);
    try { localStorage.setItem(KEY, JSON.stringify(drafts)); } catch (e) {}
  }

  function clearStore() {
    writeFrame(null);
    try { localStorage.removeItem(KEY); } catch (e) {}
  }

  /* The runtime listens on the cards it found at load. An input event on one of
   * them refreshes its summary and its "already sent" state. */
  function tellRuntime() {
    var card = form.querySelector('.afkv2-card [data-afkv2-input]');
    if (card) card.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function changed() {
    save();
    tellRuntime();
  }

  function refreshPanel() {
    panel.hidden = entries().length === 0;
    if (!panel.hidden) form.hidden = false;
  }

  function target(id) {
    return document.querySelector('[data-afkv2-element="' + CSS.escape(id) + '"]');
  }

  function radios(entry, name, options, hide) {
    var set = make('fieldset');
    set.setAttribute('data-afkv2-input', 'choice');
    set.hidden = !!hide;
    options.forEach(function (option) {
      var label = make('label'), input = make('input');
      input.type = 'radio';
      input.name = name;
      input.value = option[0];
      input.checked = !!hide;
      label.appendChild(input);
      label.appendChild(document.createTextNode(' ' + option[1]));
      set.appendChild(label);
    });
    entry.appendChild(set);
  }

  function headline(action, key) {
    if (action === EDIT) return 'Edit note ' + key;
    if (action === DELETE) return 'Delete note ' + key;
    return 'Note on ' + key;
  }

  /* An entry holds the attribute contract the runtime reads. Its state is
   * "current" so the page rail never folds it. */
  function entryFor(key, action, marks) {
    var found = panel.querySelector('[data-afkv2-item="' + CSS.escape(key) + '"]');
    if (found) return found;
    var entry = make('div', 'afkv2-note-draft');
    entry.setAttribute('data-afkv2-item', key);
    entry.setAttribute('data-afkv2-state', 'current');
    entry.setAttribute('data-afkv2-note-action', action);
    /* The page rail labels an entry with its first child: that child holds only the words. */
    entry.appendChild(make('p', 'afkv2-note-draft-head', headline(action, key)));
    var actions = make('p', 'afkv2-note-draft-actions');
    entry.appendChild(actions);
    if (action === 'note' && target(key)) {
      var go = make('button', '', 'Show it');
      go.type = 'button';
      go.addEventListener('click', function () { target(key).scrollIntoView({ block: 'center' }); });
      actions.appendChild(go);
      actions.appendChild(document.createTextNode(' '));
    }
    var drop = make('button', '', action === 'note' ? 'Delete this note' : 'Keep the note as it is');
    drop.type = 'button';
    drop.addEventListener('click', function () {
      panel.removeChild(entry);
      refreshPanel();
      changed();
    });
    actions.appendChild(drop);
    if (action === 'note') {
      if (marks) radios(entry, 'note-mark:' + key, marks);
    } else {
      radios(entry, 'note-action:' + key, [[action, action]], true);
    }
    if (action !== DELETE) {
      var field = make('textarea');
      field.rows = 3;
      field.setAttribute('data-afkv2-input', 'note');
      field.name = 'note:' + key;
      field.setAttribute('aria-label', headline(action, key));
      entry.appendChild(field);
      if (action === EDIT) {
        /* An edit down to no text is a delete: an edit line must hold text. */
        field.addEventListener('input', function () {
          entry.querySelector('input[type="radio"]').value = field.value.trim() ? EDIT : DELETE;
        });
      }
    }
    entry.addEventListener('input', changed);
    entry.addEventListener('change', changed);
    panel.appendChild(entry);
    refreshPanel();
    return entry;
  }

  function settledMarks(el) {
    if (!el || el.getAttribute('data-afkv2-state') !== 'settled') return null;
    for (var kind in SETTLED_MARKS) {
      if (el.matches('.afkv2-card--' + kind)) return SETTLED_MARKS[kind];
    }
    return null;
  }

  function open(id, el) {
    var entry = entryFor(id, 'note', settledMarks(el));
    var field = fieldOf(entry);
    entry.scrollIntoView({ block: 'center' });
    if (field) field.focus();
  }

  function addButton(el, id) {
    var button = make('button', 'afkv2-note-add', '+ note');
    button.type = 'button';
    button.setAttribute('aria-label', 'Write a note on ' + id);
    button.addEventListener('click', function (event) {
      /* The heading of a settled card also folds it. */
      event.stopPropagation();
      open(id, el);
    });
    if (el.matches('.afkv2-card')) el.querySelector('.afkv2-h').appendChild(button);
    else el.insertBefore(button, el.firstChild);
  }

  function arm(el) {
    var id = el.getAttribute('data-afkv2-element');
    if (el.matches('.afkv2-box')) {
      /* A map node is a small box with a computed size: the box itself is the control. */
      el.setAttribute('role', 'button');
      el.setAttribute('tabindex', '0');
      /* The host treats a click on a custom element as an annotation unless told. */
      el.setAttribute('data-lavish-action', 'afkv2-note');
      el.setAttribute('aria-label', 'Write a note on ' + id);
      var act = function (event) {
        if (event.target.closest('[data-afkv2-element]') !== el) return;
        open(id, el);
      };
      el.addEventListener('click', act);
      el.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); act(event); }
      });
      var figure = el.closest('figure');
      if (figure && !figure.querySelector('.afkv2-note-hint')) {
        figure.insertBefore(make('p', 'afkv2-note-hint', 'Click a node to write a note on it.'), figure.firstChild);
      }
      return;
    }
    if (el.matches('.afkv2-card') && el.querySelector(':scope > .afkv2-answer [data-afkv2-input="note"]')) return;
    addButton(el, id);
  }

  [].slice.call(document.querySelectorAll('[data-afkv2-element]')).forEach(arm);

  var notes = document.getElementById('afkv2-notes-replies');
  if (notes) {
    notes.addEventListener('click', function (event) {
      var edit = event.target.getAttribute('data-afkv2-note-edit');
      var remove = event.target.getAttribute('data-afkv2-note-delete');
      if (edit) {
        var entry = entryFor(edit, EDIT);
        var field = fieldOf(entry);
        if (!field.value) field.value = event.target.closest('[data-afkv2-note]').querySelector('.afkv2-nr-text').textContent;
        entry.scrollIntoView({ block: 'center' });
        field.focus();
        changed();
      } else if (remove) {
        entryFor(remove, DELETE).scrollIntoView({ block: 'center' });
        changed();
      }
    });
  }

  var saved = readStore();
  Object.keys(saved).forEach(function (key) {
    var draft = saved[key], action = draft.a || 'note';
    if (action === 'note' && !target(key)) return;
    if (action !== 'note' && !document.querySelector('[data-afkv2-note="' + CSS.escape(key) + '"]')) return;
    var entry = entryFor(key, action, action === 'note' ? settledMarks(target(key)) : null);
    var field = fieldOf(entry);
    if (field) field.value = draft.n || '';
    var radio = entry.querySelector('input[type="radio"]');
    if (action !== 'note' && radio) radio.value = draft.c || action;
    [].slice.call(entry.querySelectorAll('input[type="radio"]')).forEach(function (input) {
      if (draft.c && input.value === draft.c) input.checked = true;
    });
  });
  refreshPanel();
  tellRuntime();

  /* The runtime says "sent" only after the bridge took the prompt. */
  var status = bar.querySelector('.afkv2-send-status');
  if (status) {
    new MutationObserver(function () {
      if (status.textContent === 'Round R-' + round + ' sent.') clearStore();
    }).observe(status, { childList: true, characterData: true, subtree: true });
  }
})();
