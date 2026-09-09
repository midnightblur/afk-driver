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
 *   R-2  one send per round — a single queuePrompt + sendQueuedPrompts,
 *        never one per item.
 *   R-3  marks and notes persist per item id in localStorage, surviving reload
 *        and session end.
 *   R-4  the response grammar, emitted verbatim.
 *
 * Every window.lavish call is guarded: opening the file with no server running
 * must behave identically, minus the send.
 */
(function () {
  var bar = document.getElementById('afk-send');
  if (!bar) return;
  var round = bar.getAttribute('data-afk-round') || '?';
  var KEY = 'afk-round:' + location.pathname;
  var NO_CHOICE = '—';

  var store = {};
  try { store = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) {}
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(store)); } catch (e) {}
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
  function send() {
    var missing = unmarked();
    if (missing.length && !armed) {
      armed = true;
      say('No mark on ' + missing.join(', ') + ' — those stay unanswered. '
          + 'Send again to send anyway.', true);
      return;
    }
    armed = false;
    if (!window.lavish || !window.lavish.queuePrompt) {
      say('No session — use Copy and paste the response to the agent.', true);
      return;
    }
    window.lavish.queuePrompt(compose());
    if (window.lavish.sendQueuedPrompts) window.lavish.sendQueuedPrompts();
    say('Round R-' + round + ' sent.');
  }

  function copy() {
    var text = compose();
    var done = function () { say('Copied — paste it to the agent.'); };
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
    try { document.execCommand('copy'); done(); } catch (e) { say('Copy failed.', true); }
    document.body.removeChild(ta);
  }

  cards().forEach(function (el) {
    restore(el);
    el.addEventListener('change', function () { armed = false; remember(el); refreshJump(); });
    el.addEventListener('input', function () { armed = false; remember(el); refreshJump(); });
  });

  var sendBtn = bar.querySelector('#afk-send-go');
  var copyBtn = bar.querySelector('#afk-send-copy');
  if (sendBtn) sendBtn.addEventListener('click', send);
  if (copyBtn) copyBtn.addEventListener('click', copy);
  if (jumpBtn) jumpBtn.addEventListener('click', jumpToFirstUnmarked);
  refreshJump();

  var n = cards().length;
  say(n + (n === 1 ? ' card' : ' cards') + ' in this round — one send answers them all.');
})();
