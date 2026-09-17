/* Send runtime — inlined into every rendered page, never fetched.
 *
 * The page-writer never authors send logic; this file is that logic, and the
 * renderer emitting it is what makes the attribute contract true by
 * construction. It reads only the attribute contract, so a hand-authored card
 * carrying the same attributes composes identically to a rendered one.
 *
 * What it guarantees (LAVISH-KIT.md "Runtime contract"):
 *   R-1  one `data-afk-input="choice"` and one `data-afk-input="note"` per
 *        `data-afk-item` card inside the current section; native controls only.
 *   R-2  one form submit per round — a single tagged queuePrompt plus
 *        sendQueuedPrompts, never one per item.
 *   R-3  marks and notes persist by session path and item id in localStorage.
 *   R-4  the response grammar, emitted verbatim.
 *
 * Every window.lavish call is guarded: opening the file with no server running
 * must behave identically, minus the send.
 */
(function () {
  var bar = document.getElementById('afk-send');
  if (!bar) return;
  var form = document.getElementById('afk-answer-form');
  if (!form) return;
  var round = bar.getAttribute('data-afk-round') || '?';
  /* The namespace contains no page-revision token. A render revision must not
   * silently discard marks made against the same session and item ids. */
  var KEY = 'afk-answers:' + location.pathname;
  var LEGACY_KEY = 'afk-round:' + location.pathname;
  var NO_CHOICE = '—';

  /* Two stores, because the first one is not always there. A host may load this
   * page in a sandboxed frame with an opaque origin, where every `localStorage`
   * call throws — and a guarded call that throws loses the draft in silence,
   * which is the one failure mode nobody is told about. `window.name` survives a
   * navigation of the same browsing context, an `src` reset included, and an
   * opaque origin can still read and write it. So marks go to both: whichever
   * one the host allows is the one that answers on the way back.
   *
   * A reload costs the human nothing only if this holds. It is the reason the
   * page can be re-rendered at all. */
  function frameRead() {
    try {
      var envelope = JSON.parse(window.name || '{}') || {};
      var drafts = envelope.afkAnswers;
      return (drafts && drafts[KEY]) || null;
    } catch (e) { return null; }
  }

  function frameWrite(value) {
    try {
      var envelope = {};
      try { envelope = JSON.parse(window.name || '{}') || {}; } catch (e) {}
      /* Another page's name payload is not ours to drop. */
      if (!envelope.afkAnswers) envelope.afkAnswers = {};
      envelope.afkAnswers[KEY] = value;
      window.name = JSON.stringify(envelope);
      return true;
    } catch (e) { return false; }
  }

  function localRead() {
    try {
      var stored = localStorage.getItem(KEY);
      if (!stored) {
        stored = localStorage.getItem(LEGACY_KEY);
        if (stored) migrateLegacy = true;
      }
      return JSON.parse(stored || '{}') || {};
    } catch (e) { return null; }
  }

  var migrateLegacy = false;
  /* The frame store wins a tie: it is written last and cannot go stale behind a
   * `localStorage` copy the host silently refused to update. */
  var store = frameRead() || localRead() || {};

  function save() {
    var text;
    try { text = JSON.stringify(store); } catch (e) { return false; }
    var kept = frameWrite(store);
    try {
      localStorage.setItem(KEY, text);
      kept = true;
    } catch (e) {}
    return kept;
  }
  if (migrateLegacy && save()) {
    try { localStorage.removeItem(LEGACY_KEY); } catch (e) {}
  }

  /* Page order = DOM order, and only cards inside the current section are the
   * round's questions; settled and carried-over cards answer nothing. */
  function cards() {
    var current = document.querySelector('[data-afk-state="current"]');
    if (!current) return [];
    return [].slice.call(current.querySelectorAll('[data-afk-item]')).filter(function (el) {
      return el.querySelector('[data-afk-input="choice"], [data-afk-input="note"]');
    });
  }

  function choiceOf(el) {
    var host = el.querySelector('[data-afk-input="choice"]');
    if (!host) return '';
    var picked = host.querySelector('input[type="radio"]:checked');
    return picked ? picked.value : '';
  }

  function noteOf(el) {
    var field = el.querySelector('[data-afk-input="note"]');
    return field ? field.value.trim() : '';
  }

  function restore(el) {
    var id = el.getAttribute('data-afk-item');
    var saved = store[id];
    if (!saved) return;
    var host = el.querySelector('[data-afk-input="choice"]');
    if (host && saved.c) {
      var radios = host.querySelectorAll('input[type="radio"]');
      for (var i = 0; i < radios.length; i++) {
        if (radios[i].value === saved.c) { radios[i].checked = true; break; }
      }
    }
    var field = el.querySelector('[data-afk-input="note"]');
    if (field && saved.n) field.value = saved.n;
  }

  function remember(el) {
    var id = el.getAttribute('data-afk-item');
    var c = choiceOf(el), n = noteOf(el);
    if (!c && !n) { delete store[id]; } else { store[id] = { c: c, n: n }; }
    save();
  }

  /* R-4. One line per card, page order; an em dash stands for no choice, and
   * the note follows a pipe only when there is one. */
  function compose() {
    var lines = ['[round R-' + round + ']'];
    cards().forEach(function (el) {
      var id = el.getAttribute('data-afk-item');
      var c = choiceOf(el) || NO_CHOICE;
      var n = noteOf(el);
      lines.push(n ? id + ' ' + c + ' | ' + n : id + ' ' + c);
    });
    return lines.join('\n');
  }

  function answerData() {
    return cards().map(function (el) {
      return {
        id: el.getAttribute('data-afk-item'),
        choice: choiceOf(el) || '',
        note: noteOf(el)
      };
    });
  }

  var summary = bar.querySelector('#afk-send-summary');
  function refreshSummary() {
    if (!summary) return;
    summary.textContent = answerData().map(function (answer) {
      return answer.id + '=' + (answer.choice || NO_CHOICE);
    }).join(' · ');
  }

  /* Silence is not agreement. Every answerable card carries the required flag,
   * so a card with no mark is unanswered rather than accepted. The human is
   * told which ones before the send, and can still send. */
  function unmarkedCards() {
    return cards().filter(function (el) {
      return el.getAttribute('data-afk-required') === '1' && !choiceOf(el);
    });
  }

  function unmarked() {
    return unmarkedCards().map(function (el) { return el.getAttribute('data-afk-item'); });
  }

  /* Round size follows what is being decided, so nothing caps the card count.
   * Navigation is what keeps a long round readable: the bar names every
   * unmarked card and this control walks to them, first one first. */
  var jumpBtn = bar.querySelector('#afk-send-jump');
  function refreshJump() {
    if (!jumpBtn) return;
    var pending = unmarkedCards();
    jumpBtn.hidden = pending.length === 0;
    jumpBtn.textContent = pending.length === 1
      ? 'Go to the unmarked card'
      : 'Go to first of ' + pending.length + ' unmarked';
  }

  function jumpToFirstUnmarked() {
    var pending = unmarkedCards();
    if (!pending.length) return;
    var target = pending[0];
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    target.classList.add('afk-seek');
    setTimeout(function () { target.classList.remove('afk-seek'); }, 1600);
    var radio = target.querySelector('[data-afk-input="choice"] input[type="radio"]');
    if (radio && radio.focus) radio.focus({ preventScroll: true });
  }

  var status = bar.querySelector('.afk-send-status');
  function say(text, warn) {
    if (!status) return;
    status.textContent = text;
    status.classList.toggle('afk-warn', !!warn);
  }

  var armed = false;
  var sent = false;
  function send() {
    if (sent) {
      say('Already sent. Change an answer, or use Copy the response.');
      return;
    }
    var missing = unmarked();
    if (missing.length && !armed) {
      armed = true;
      say('No mark on ' + missing.join(', ') + ' — those stay unanswered. '
          + 'Send again to send anyway.', true);
      return;
    }
    armed = false;
    var bridge = window.lavish;
    if (!bridge || typeof bridge.queuePrompt !== 'function' ||
        typeof bridge.sendQueuedPrompts !== 'function') {
      copy('No session. Copied the answers. Paste them to the agent.');
      return;
    }
    /* afk:send-bridge */
    bridge.queuePrompt(compose(), {
      tag: 'choice',
      text: 'Round R-' + round + ' answers',
      element: form
    });
    bridge.sendQueuedPrompts();
    sent = true;
    say('Round R-' + round + ' sent.');
  }

  function copy(message) {
    var text = compose();
    var done = function () {
      say(message || 'Copied. Paste it to the agent.');
    };
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
      if (document.execCommand('copy')) {
        done();
      } else {
        say('Copy failed.', true);
      }
    } catch (e) { say('Copy failed.', true); }
    document.body.removeChild(ta);
  }

  cards().forEach(function (el) {
    restore(el);
    el.addEventListener('change', function () {
      armed = false; remember(el); refreshJump(); refreshSummary();
      if (sent) {
        sent = false;
        say('Answers changed after send. Send them again.', true);
      }
    });
    el.addEventListener('input', function () {
      armed = false; remember(el); refreshJump(); refreshSummary();
      if (sent) {
        sent = false;
        say('Answers changed after send. Send them again.', true);
      }
    });
  });

  var copyBtn = bar.querySelector('#afk-send-copy');
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    send();
  });
  if (copyBtn) copyBtn.addEventListener('click', function () { copy(); });
  if (jumpBtn) jumpBtn.addEventListener('click', jumpToFirstUnmarked);
  refreshJump();
  refreshSummary();

  var n = cards().length;
  say(n + (n === 1 ? ' card' : ' cards') + ' in this round — one send answers them all.');
})();
