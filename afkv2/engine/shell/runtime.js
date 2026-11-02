/* Send runtime, inlined into every rendered page, never fetched.
 *
 * It reads only the attribute contract the card component emits. One form
 * submit per round sends one tagged prompt. Every window.lavish call is
 * guarded: opening the file with no server behaves the same, minus the send.
 *
 * The response grammar: first line [round R-n], then one line per card in
 * page order, <id> <token> or <id> <token> | <note>; an em dash stands for
 * no choice.
 */
(function () {
  var bar = document.getElementById('afkv2-send');
  if (!bar) return;
  var form = document.getElementById('afkv2-answer-form');
  if (!form) return;
  var round = bar.getAttribute('data-afkv2-round') || '?';
  /* A browser draft is keyed by session id and round, so a re-render keeps it
   * and the next round starts empty. */
  var KEY_PREFIX = 'afkv2-draft:';
  var KEY = KEY_PREFIX + bar.getAttribute('data-afkv2-session') + ':' + round;
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
      var drafts = envelope.afkv2Answers;
      return (drafts && drafts[KEY]) || null;
    } catch (e) { return null; }
  }

  function frameWrite(value) {
    try {
      var envelope = {};
      try { envelope = JSON.parse(window.name || '{}') || {}; } catch (e) {}
      /* Another page's name payload is not ours to drop. */
      if (!envelope.afkv2Answers) envelope.afkv2Answers = {};
      envelope.afkv2Answers[KEY] = value;
      window.name = JSON.stringify(envelope);
      return true;
    } catch (e) { return false; }
  }

  function localRead() {
    try {
      return JSON.parse(localStorage.getItem(KEY) || '{}') || {};
    } catch (e) { return null; }
  }

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

  /* A sent round needs no draft: the next page state comes from the document. */
  function clearDraft() {
    store = {};
    frameWrite(store);
    try { localStorage.removeItem(KEY); } catch (e) {}
  }

  /* Page order = DOM order, and only cards inside the current section are the
   * round's questions; settled and carried-over cards answer nothing. */
  function cards() {
    var current = document.querySelector('[data-afkv2-state="current"]');
    if (!current) return [];
    return [].slice.call(current.querySelectorAll('[data-afkv2-item]')).filter(function (el) {
      return el.querySelector('[data-afkv2-input="choice"], [data-afkv2-input="note"]');
    });
  }

  function choiceOf(el) {
    var host = el.querySelector('[data-afkv2-input="choice"]');
    if (!host) return '';
    var picked = host.querySelector('input[type="radio"]:checked');
    return picked ? picked.value : '';
  }

  function noteOf(el) {
    var field = el.querySelector('[data-afkv2-input="note"]');
    return field ? field.value.trim() : '';
  }

  function restore(el) {
    var id = el.getAttribute('data-afkv2-item');
    var saved = store[id];
    if (!saved) return;
    var host = el.querySelector('[data-afkv2-input="choice"]');
    if (host && saved.c) {
      var radios = host.querySelectorAll('input[type="radio"]');
      for (var i = 0; i < radios.length; i++) {
        if (radios[i].value === saved.c) { radios[i].checked = true; break; }
      }
    }
    var field = el.querySelector('[data-afkv2-input="note"]');
    if (field && saved.n) field.value = saved.n;
  }

  function remember(el) {
    var id = el.getAttribute('data-afkv2-item');
    var c = choiceOf(el), n = noteOf(el);
    if (!c && !n) { delete store[id]; } else { store[id] = { c: c, n: n }; }
    save();
  }

  /* One line per card, page order; an em dash stands for no choice, and the
   * note follows a pipe only when there is one. */
  function compose() {
    var lines = ['[round R-' + round + ']'];
    cards().forEach(function (el) {
      var id = el.getAttribute('data-afkv2-item');
      var c = choiceOf(el) || NO_CHOICE;
      var n = noteOf(el);
      lines.push(n ? id + ' ' + c + ' | ' + n : id + ' ' + c);
    });
    return lines.join('\n');
  }

  function answerData() {
    return cards().map(function (el) {
      return {
        id: el.getAttribute('data-afkv2-item'),
        choice: choiceOf(el) || '',
        note: noteOf(el)
      };
    });
  }

  var summary = bar.querySelector('#afkv2-send-summary');
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
      return el.getAttribute('data-afkv2-required') === '1' && !choiceOf(el);
    });
  }

  function unmarked() {
    return unmarkedCards().map(function (el) { return el.getAttribute('data-afkv2-item'); });
  }

  /* Round size follows what is being decided, so nothing caps the card count.
   * Navigation is what keeps a long round readable: the bar names every
   * unmarked card and this control walks to them, first one first. */
  var jumpBtn = bar.querySelector('#afkv2-send-jump');
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
    target.classList.add('afkv2-seek');
    setTimeout(function () { target.classList.remove('afkv2-seek'); }, 1600);
    var radio = target.querySelector('[data-afkv2-input="choice"] input[type="radio"]');
    if (radio && radio.focus) radio.focus({ preventScroll: true });
  }

  var status = bar.querySelector('.afkv2-send-status');
  function say(text, warn) {
    if (!status) return;
    status.textContent = text;
    status.classList.toggle('afkv2-warn', !!warn);
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
    bridge.queuePrompt(compose(), {
      tag: 'choice',
      text: 'Round R-' + round + ' answers',
      element: form
    });
    bridge.sendQueuedPrompts();
    clearDraft();
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

  var copyBtn = bar.querySelector('#afkv2-send-copy');
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
