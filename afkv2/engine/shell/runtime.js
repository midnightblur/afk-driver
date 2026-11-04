/* Mark runtime, inlined into every rendered page, never fetched.
 *
 * A mark radio queues one prompt `<card id> <token>` with the lavish bridge.
 * Its queue key names the session, the round and the card, so a new mark
 * replaces the unsent mark of the same card. A note is a native lavish
 * annotation. The human sends marks and annotations with lavish's own Send.
 *
 * Without lavish, "Copy the response" composes the response grammar from the
 * marks: first line [round R-n], then one line <id> <token> per marked card.
 */

/* Open folds survive a re-render. lavish restores the scroll offset after a live
 * reload, and that offset points at the same place only when the same folds are
 * open. A fold is a details element with a stable data-afkv2-fold key; the open
 * keys are stored per session in window.name and in localStorage. */
(function () {
  var holder = document.querySelector('[data-afkv2-session]');
  if (!holder) return;
  var ATTR = 'data-afkv2-fold';
  var KEY = 'afkv2-open:' + holder.getAttribute('data-afkv2-session');
  var folds = [].slice.call(document.querySelectorAll('details[' + ATTR + ']'));

  function read() {
    try {
      var held = JSON.parse(window.name || '{}') || {};
      if (held[KEY]) return held[KEY];
    } catch (e) {}
    try { return JSON.parse(localStorage.getItem(KEY) || '[]') || []; } catch (e) { return []; }
  }

  function write() {
    var open = folds.filter(function (el) { return el.open; }).map(function (el) { return el.getAttribute(ATTR); });
    try {
      var held = JSON.parse(window.name || '{}') || {};
      held[KEY] = open;
      window.name = JSON.stringify(held);
    } catch (e) {}
    try { localStorage.setItem(KEY, JSON.stringify(open)); } catch (e) {}
  }

  var open = read();
  folds.forEach(function (el) {
    if (open.indexOf(el.getAttribute(ATTR)) >= 0) el.open = true;
    el.addEventListener('toggle', write);
  });
})();

(function () {
  var section = document.querySelector('[data-afkv2-session][data-afkv2-round]');
  if (!section) return;
  var round = section.getAttribute('data-afkv2-round');
  var session = section.getAttribute('data-afkv2-session');
  /* A browser draft is keyed by session id and round, so a re-render keeps the
   * marks and the next round starts empty. In a lavish session, lavish itself
   * keeps the picked radios (data-lavish-question) and the queued marks in its
   * tab store, so they come back after a reload of the tab too. */
  var KEY_PREFIX = 'afkv2-draft:' + session + ':';
  var KEY = KEY_PREFIX + round;
  var MARK_TAG = 'afkv2-mark';

  /* Two stores, because the first one is not always there. A host may load this
   * page in a sandboxed frame with an opaque origin, where every `localStorage`
   * call throws. `window.name` survives a navigation of the same browsing
   * context, and an opaque origin can still read and write it. */
  function envelope() {
    try { return JSON.parse(window.name || '{}') || {}; } catch (e) { return {}; }
  }

  function frameWrite(value) {
    try {
      var held = envelope();
      /* Another page's name payload is not ours to drop. */
      var drafts = held.afkv2Answers || {};
      Object.keys(drafts).forEach(function (key) {
        if (key.indexOf(KEY_PREFIX) === 0 && key !== KEY) delete drafts[key];
      });
      drafts[KEY] = value;
      held.afkv2Answers = drafts;
      window.name = JSON.stringify(held);
    } catch (e) {}
  }

  function localRead() {
    try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { return {}; }
  }

  /* The frame store wins a tie: it is written last. */
  var store = ((envelope().afkv2Answers || {})[KEY]) || localRead();

  function save() {
    frameWrite(store);
    try {
      for (var i = localStorage.length - 1; i >= 0; i--) {
        var key = localStorage.key(i);
        if (key && key.indexOf(KEY_PREFIX) === 0 && key !== KEY) localStorage.removeItem(key);
      }
      localStorage.setItem(KEY, JSON.stringify(store));
    } catch (e) {}
  }

  /* Page order = DOM order; only the cards of the current round take a mark. */
  function cards() {
    return [].slice.call(section.querySelectorAll('[data-afkv2-item]')).filter(function (el) {
      return el.querySelector('[data-afkv2-input="choice"]');
    });
  }

  function choiceOf(el) {
    var picked = el.querySelector('[data-afkv2-input="choice"] input[type="radio"]:checked');
    return picked ? picked.value : '';
  }

  function restore(el) {
    var saved = store[el.getAttribute('data-afkv2-item')];
    if (!saved) return;
    var radios = el.querySelectorAll('[data-afkv2-input="choice"] input[type="radio"]');
    for (var i = 0; i < radios.length; i++) {
      if (radios[i].value === saved) { radios[i].checked = true; break; }
    }
  }

  var bar = document.getElementById('afkv2-copy');
  var status = bar && bar.querySelector('.afkv2-copy-status');
  function say(text) {
    if (status) status.textContent = text;
  }

  function queue(el, id, token) {
    var bridge = window.lavish;
    if (!bridge || typeof bridge.queuePrompt !== 'function') return false;
    bridge.queuePrompt(id + ' ' + token, {
      tag: MARK_TAG,
      queueKey: 'afkv2:' + session + ':' + round + ':' + id,
      element: el,
      data: { item: id, mark: token }
    });
    return true;
  }

  function compose() {
    var lines = ['[round R-' + round + ']'];
    cards().forEach(function (el) {
      var token = choiceOf(el);
      if (token) lines.push(el.getAttribute('data-afkv2-item') + ' ' + token);
    });
    return lines.join('\n');
  }

  function copy() {
    var text = compose();
    var done = function () { say('Copied. Paste it to the agent. For a note, add a line <id> note 1 (2, 3 for more notes on the same id), then your words on the next lines, each indented 2 spaces.'); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { fallback(text, done); });
    } else {
      fallback(text, done);
    }
  }

  function fallback(text, done) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try {
      if (document.execCommand('copy')) done(); else say('Copy failed.');
    } catch (e) { say('Copy failed.'); }
    document.body.removeChild(ta);
  }

  cards().forEach(function (el) {
    restore(el);
    el.addEventListener('change', function (event) {
      if (!event.target.matches('input[type="radio"]')) return;
      var id = el.getAttribute('data-afkv2-item');
      var token = choiceOf(el);
      store[id] = token;
      save();
      say(queue(el, id, token)
        ? 'Queued ' + id + ' ' + token + '. Send it with the rest in the lavish panel.'
        : 'No lavish session: use Copy the response.');
    });
  });

  var copyBtn = document.getElementById('afkv2-copy-go');
  if (copyBtn) copyBtn.addEventListener('click', copy);
})();

/* Back after a jump. An in-page link, a map box and the rail jump through
 * jump(), which first keeps the place the window shows. The page keeps its own
 * list of the last 20 places, per session, in window.name and in localStorage,
 * as the folds are kept: the host's sandboxed frame owns no browser history.
 * A place is the nearest element with an id at the top of the window and its
 * offset, so it survives a re-render that moves the content. */
(function () {
  var holder = document.querySelector('[data-afkv2-session]');
  if (!holder || !document.body) return;
  var BACK_LIMIT = 20;
  var KEY = 'afkv2-back:' + holder.getAttribute('data-afkv2-session');
  var FLASH = 'afkv2-flash', COLLAPSED = 'afkv2-collapsed', TIP = 'data-afkv2-tip';
  var PAGE = document.querySelector('.afkv2-page');

  function read() {
    try {
      var held = JSON.parse(window.name || '{}') || {};
      if (Array.isArray(held[KEY])) return held[KEY];
    } catch (e) {}
    try { return JSON.parse(localStorage.getItem(KEY) || '[]') || []; } catch (e) { return []; }
  }

  var afkv2BackList = read();

  function write() {
    try {
      var held = JSON.parse(window.name || '{}') || {};
      held[KEY] = afkv2BackList;
      window.name = JSON.stringify(held);
    } catch (e) {}
    try { localStorage.setItem(KEY, JSON.stringify(afkv2BackList)); } catch (e) {}
  }

  var back = document.createElement('button');
  back.type = 'button';
  back.id = 'afkv2-back';
  back.setAttribute('data-lavish-ui', 'afkv2-back');
  back.textContent = '\u2190 Back';
  back.title = 'Back to where you were before the last jump';
  function refresh() { back.hidden = !afkv2BackList.length; }
  refresh();
  document.body.appendChild(back);

  /* The rail and the buttons are fixed over the page, so only a hit inside the page names a place. */
  function place() {
    var hits = document.elementsFromPoint ? document.elementsFromPoint(Math.round(window.innerWidth / 2), 8) : [];
    var at = null;
    for (var i = 0; i < hits.length && !at; i++) if (PAGE && PAGE !== hits[i] && PAGE.contains(hits[i])) at = hits[i];
    while (at && at !== PAGE && !at.id) at = at.parentElement;
    if (at === PAGE) at = null;
    return { id: at ? at.id : '', dy: at ? Math.round(at.getBoundingClientRect().top) : 0, y: Math.round(window.scrollY) };
  }

  /* An element in a closed fold or a folded card opens before the scroll. */
  function reveal(el) {
    for (var up = el; up; up = up.parentElement) {
      if (up.tagName === 'DETAILS') up.open = true;
      if (up.classList && up.classList.contains(COLLAPSED)) up.classList.remove(COLLAPSED);
    }
  }

  function jump(el) {
    if (!el) return;
    afkv2BackList.push(place());
    if (afkv2BackList.length > BACK_LIMIT) afkv2BackList.splice(0, afkv2BackList.length - BACK_LIMIT);
    write();
    refresh();
    reveal(el);
    el.scrollIntoView({ block: 'start' });
    el.classList.add(FLASH);
    setTimeout(function () { el.classList.remove(FLASH); }, 1600);
  }

  function goBack() {
    var to = afkv2BackList.pop();
    write();
    refresh();
    if (!to) return;
    var el = to.id && document.getElementById(to.id);
    if (el) {
      reveal(el);
      window.scrollTo(0, window.scrollY + el.getBoundingClientRect().top - to.dy);
    } else {
      window.scrollTo(0, to.y);
    }
  }

  back.addEventListener('click', goBack);
  window.afkv2Jump = jump;

  document.addEventListener('click', function (event) {
    var link = event.target && event.target.closest && event.target.closest('a[href^="#"]');
    if (!link) return;
    var el = document.getElementById(decodeURIComponent(link.getAttribute('href').slice(1)));
    if (!el) return;
    event.preventDefault();
    jump(el);
  });

  /* A map box opens its card. Its hover names the card, the card's state and
   * the round of its last change. */
  var cards = {};
  try { cards = JSON.parse(document.getElementById('afkv2-node-cards').textContent) || {}; } catch (e) {}
  Object.keys(cards).forEach(function (node) {
    var box = document.getElementById(node), target = document.getElementById(cards[node][0]);
    if (!box || !target) return;
    /* The heading is the card's first child; a card in its history holds headings of its own. */
    var heading = target.firstElementChild;
    var title = heading && heading.querySelector('.afkv2-card-title');
    var stateWord = heading && heading.querySelector('.afkv2-state');
    var name = title ? title.textContent.trim() : cards[node][0];
    var state = stateWord ? stateWord.textContent.trim() : target.getAttribute('data-afkv2-point');
    /* The tooltip layer shows data-afkv2-tip; a title would give the box its dotted tip underline. */
    box.setAttribute(TIP, name + ': ' + state + ', last changed in round ' + cards[node][1] + '. Click to open the card.');
    box.classList.add('afkv2-box--card');
    box.addEventListener('click', function () { jump(target); });
  });
})();
