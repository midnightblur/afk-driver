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
(function () {
  var section = document.querySelector('[data-afkv2-session][data-afkv2-round]');
  if (!section) return;
  var round = section.getAttribute('data-afkv2-round');
  var session = section.getAttribute('data-afkv2-session');
  /* A browser draft is keyed by session id and round, so a re-render keeps the
   * marks and the next round starts empty. */
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
    var done = function () { say('Copied. Paste it to the agent, and add a note line <id> — | <note> where you need one.'); };
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
