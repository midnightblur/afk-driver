/* Mark runtime, inlined into every rendered page, never fetched.
 *
 * A mark radio queues one prompt `<card id> <token>` with the lavish bridge.
 * Its queue key names the session, the round and the card, so a new mark
 * replaces the unsent mark of the same card. A write-in queues its typed words
 * on the lines after `<card id> write-in`; with no words it queues the bare line
 * with `words: ''` in its data, which the engine's poll drops: a write-in with no
 * words is never sent, and it replaces an earlier mark of the card. A note is a native lavish
 * annotation. The human sends marks and annotations with lavish's own Send.
 * A question for others queues 1 tick line `<question id> tick <option id> ...` in tick order, replaced on
 * each change (ADR-0004 design); with no tick left, the line names no option and sends nothing.
 *
 * Without lavish, "Copy the response" composes the response grammar from the
 * marks: first line [round R-n], then one line <id> <token> per marked card, a write-in's words as its
 * note 1, then each tick line.
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
  /* A question id names its ticks in the draft; a card id names its mark. */
  var TICK_KEY = 'tick:';
  /* A card id names its write-in words in the draft. */
  var WORDS_KEY = 'words:';
  var WRITE_IN = 'write-in';

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

  function wordsBox(el) {
    return el.querySelector('[data-afkv2-input="' + WRITE_IN + '"]');
  }

  function wordsOf(el) {
    var box = wordsBox(el);
    return box ? String(box.value || '').replace(/\r\n/g, '\n').replace(/\s+$/, '').replace(/^\s*\n/, '') : '';
  }

  function restore(el) {
    var id = el.getAttribute('data-afkv2-item');
    var box = wordsBox(el);
    if (box && !box.value && store[WORDS_KEY + id]) box.value = store[WORDS_KEY + id];
    var saved = store[id];
    if (!saved) return;
    var radios = el.querySelectorAll('[data-afkv2-input="choice"] input[type="radio"]');
    for (var i = 0; i < radios.length; i++) {
      if (radios[i].value === saved) { radios[i].checked = true; break; }
    }
  }

  /* The questions for others sit outside the round's block, so the page holds their tick groups. */
  function tickGroups() {
    return [].slice.call(document.querySelectorAll('[data-afkv2-input="tick"][data-afkv2-question]'));
  }

  /* The tick order also sits in a hidden input of the group: the host frame keeps no storage over a reload,
   * and lavish sets each control of a lavish question again, this input too, with no change event. */
  var ORDER_ATTR = 'data-afkv2-tick-order';

  function boxes(group) {
    return [].slice.call(group.querySelectorAll('input')).filter(function (box) { return box.type !== 'hidden'; });
  }

  function orderInput(group) {
    var input = group.querySelector('input[' + ORDER_ATTR + ']');
    if (!input) {
      input = document.createElement('input');
      input.type = 'hidden';
      input.setAttribute(ORDER_ATTR, '');
      group.appendChild(input);
    }
    return input;
  }

  function heldOrder(group) {
    try {
      var kept = JSON.parse(orderInput(group).value || 'null');
      if (Array.isArray(kept)) return kept;
    } catch (e) {}
    var saved = store[TICK_KEY + group.getAttribute('data-afkv2-question')];
    return Array.isArray(saved) ? saved : [];
  }

  /* The held tick order, less each option no longer ticked, + each new tick at the end. */
  function ticksOf(group) {
    var on = boxes(group).filter(function (box) { return box.checked; }).map(function (box) { return box.value; });
    var held = heldOrder(group).filter(function (value) { return on.indexOf(value) >= 0; });
    on.forEach(function (value) { if (held.indexOf(value) < 0) held.push(value); });
    return held;
  }

  function keepOrder(group, ticks) {
    orderInput(group).value = JSON.stringify(ticks);
  }

  function restoreTicks(group) {
    var saved = store[TICK_KEY + group.getAttribute('data-afkv2-question')];
    if (!Array.isArray(saved)) return;
    boxes(group).forEach(function (box) { box.checked = saved.indexOf(box.value) >= 0; });
    keepOrder(group, saved);
  }

  function tickLine(id, ticks) {
    return [id, 'tick'].concat(ticks).join(' ');
  }

  var bar = document.getElementById('afkv2-copy');
  var status = bar && bar.querySelector('.afkv2-copy-status');
  function say(text) {
    if (status) status.textContent = text;
  }

  function queue(el, id, token) {
    var bridge = window.lavish;
    if (!bridge || typeof bridge.queuePrompt !== 'function') return false;
    var data = { item: id, mark: token };
    var words = '';
    if (token === WRITE_IN) {
      words = wordsOf(el);
      data.words = words;
    }
    bridge.queuePrompt(id + ' ' + token + (words ? '\n' + words : ''), {
      tag: MARK_TAG,
      queueKey: 'afkv2:' + session + ':' + round + ':' + id,
      element: el,
      data: data
    });
    return true;
  }

  function queued(el, id, token) {
    if (!queue(el, id, token)) return 'No lavish session: use Copy the response.';
    if (token === WRITE_IN && !wordsOf(el)) return 'Type your words for ' + id + ': a write-in with no words is not sent.';
    return 'Queued ' + id + ' ' + token + (token === WRITE_IN ? ' with your words' : '') +
      '. Send it with the rest in the lavish panel.';
  }

  function queueTicks(group, id, ticks) {
    var bridge = window.lavish;
    if (!bridge || typeof bridge.queuePrompt !== 'function') return false;
    bridge.queuePrompt(tickLine(id, ticks), {
      tag: 'afkv2-tick',
      queueKey: 'afkv2:' + session + ':' + round + ':' + TICK_KEY + id,
      element: group.closest('article') || group,
      data: { question: id, ticks: ticks }
    });
    return true;
  }

  function compose() {
    var lines = ['[round R-' + round + ']'];
    cards().forEach(function (el) {
      var token = choiceOf(el), id = el.getAttribute('data-afkv2-item');
      if (!token) return;
      if (token !== WRITE_IN) { lines.push(id + ' ' + token); return; }
      var words = wordsOf(el);
      if (!words) return;
      lines.push(id + ' ' + token, id + ' note 1');
      words.split('\n').forEach(function (line) { lines.push('  ' + line); });
    });
    tickGroups().forEach(function (group) {
      var ticks = ticksOf(group);
      if (ticks.length) lines.push(tickLine(group.getAttribute('data-afkv2-question'), ticks));
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
      say(queued(el, id, token));
    });
    /* Each typed change re-queues the write-in on the same key, so the last words win. */
    el.addEventListener('input', function (event) {
      if (!event.target.matches('[data-afkv2-input="' + WRITE_IN + '"]')) return;
      var id = el.getAttribute('data-afkv2-item');
      store[WORDS_KEY + id] = wordsOf(el);
      save();
      if (choiceOf(el) === WRITE_IN) say(queued(el, id, WRITE_IN));
    });
  });

  tickGroups().forEach(function (group) {
    /* The host frame keeps no storage over a reload; lavish sets the controls of a lavish question again. */
    group.setAttribute('data-lavish-question', TICK_KEY + group.getAttribute('data-afkv2-question'));
    orderInput(group);
    restoreTicks(group);
    group.addEventListener('change', function (event) {
      if (!event.target.matches('input')) return;
      var id = group.getAttribute('data-afkv2-question');
      var ticks = ticksOf(group);
      store[TICK_KEY + id] = ticks;
      keepOrder(group, ticks);
      save();
      if (!queueTicks(group, id, ticks)) say('No lavish session: use Copy the response.');
      else say(ticks.length ? 'Queued your ticks on this question. Send them with the rest in the lavish panel.'
        : 'No tick on this question: it sends nothing.');
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

  /* The page writes each in-page id raw into its href, so the id is the href less its '#'. */
  var IN_PAGE_LINK = 'a[href^="#"]';
  document.addEventListener('click', function (event) {
    var link = event.target && event.target.closest && event.target.closest(IN_PAGE_LINK);
    if (!link) return;
    var el = document.getElementById(link.getAttribute('href').slice(1));
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
    /* The heading is the first child of the card body; a card in its history holds headings of its own. */
    var heading = target.querySelector(':scope > .afkv2-card-body > .afkv2-h');
    var title = heading && heading.querySelector('.afkv2-card-title');
    var stateWord = heading && heading.querySelector('.afkv2-state');
    var name = title ? title.textContent.trim() : cards[node][0];
    var state = stateWord ? stateWord.textContent.trim() : target.getAttribute('data-afkv2-point');
    /* The tooltip layer shows data-afkv2-tip; a title would give the box its dotted tip underline. */
    box.setAttribute(TIP, name + ': ' + state + ', last changed in round ' + cards[node][1] + '. Click to open the card.');
    box.classList.add('afkv2-box--card');
    box.addEventListener('click', function (event) {
      /* A link in the box label does its own work: a card link jumps, a reference opens its tab. */
      if (event.target.closest && event.target.closest('a[href]')) return;
      jump(target);
    });
  });
})();

/* The role filter of the questions for others: a role shows its own questions and the questions for everyone,
 * in page order. It only hides questions, so it queues nothing (SDD §9 row "Filter"). */
(function () {
  var filter = document.getElementById('afkv2-who-filter');
  if (!filter) return;
  var EVERYONE = 'everyone';
  var questions = [].slice.call(document.querySelectorAll('article[data-afkv2-question]'));

  function roles(el) {
    try { return JSON.parse(el.getAttribute('data-afkv2-who') || '[]') || []; } catch (e) { return []; }
  }

  function show() {
    var role = filter.value;
    questions.forEach(function (el) {
      var who = roles(el);
      el.hidden = !!role && who.indexOf(role) < 0 && who.indexOf(EVERYONE) < 0;
    });
  }

  filter.addEventListener('change', show);
  show();
})();
