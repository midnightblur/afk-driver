/* Side-question control, inlined into every rendered page, never fetched.
 *
 * A floating "btw" button opens a small panel: one textarea and one Ask
 * button. Ask queues the question with the tag `afkv2-btw` and sends at once.
 * The wait answers it and shows the answer in the lavish panel; the round
 * stays open. lavish's send takes the whole queue: queued marks and notes go
 * with the question. The control is absent without the lavish bridge.
 */
(function () {
  var BTW_TAG = 'afkv2-btw';
  var tries = 0;

  function build() {
    if (document.getElementById('afkv2-btw')) return;
    var bridge = window.lavish;
    if (!bridge || typeof bridge.queuePrompt !== 'function' || !document.body) {
      if (tries++ < 20) setTimeout(build, 250);
      return;
    }
    var host = document.createElement('div');
    host.id = 'afkv2-btw';
    host.setAttribute('data-lavish-ui', 'afkv2-btw');
    var panel = document.createElement('div');
    panel.id = 'afkv2-btw-panel';
    panel.hidden = true;
    var question = document.createElement('textarea');
    question.id = 'afkv2-btw-q';
    question.rows = 1;
    question.placeholder = 'A side question about this page';
    question.setAttribute('aria-label', 'Side question');
    var hint = document.createElement('p');
    hint.className = 'afkv2-btw-hint';
    hint.textContent = 'Ask sends at once, with the marks and notes you queued. The round stays open.';
    var row = document.createElement('div');
    var ask = document.createElement('button');
    ask.type = 'button';
    ask.id = 'afkv2-btw-ask';
    ask.textContent = 'Ask';
    var status = document.createElement('output');
    status.className = 'afkv2-btw-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    row.appendChild(status);
    row.appendChild(ask);
    panel.appendChild(question);
    panel.appendChild(hint);
    panel.appendChild(row);
    var open = document.createElement('button');
    open.type = 'button';
    open.id = 'afkv2-btw-open';
    open.textContent = 'btw?';
    open.title = 'Ask a side question. The agent answers it in the lavish panel.';
    host.appendChild(panel);
    host.appendChild(open);
    document.body.appendChild(host);

    open.addEventListener('click', function () {
      panel.hidden = !panel.hidden;
      if (!panel.hidden) question.focus();
    });
    function send() {
      var text = question.value.trim();
      if (!text) return;
      bridge.queuePrompt(text, { tag: BTW_TAG, element: host });
      bridge.sendQueuedPrompts();
      question.value = '';
      status.textContent = 'Asked. The answer shows in the lavish panel.';
    }
    ask.addEventListener('click', send);
    question.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); send(); }
    });
  }

  build();
})();
