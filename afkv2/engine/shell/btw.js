/* Side-question control, inlined into every rendered page, never fetched.
 *
 * A floating "btw" button opens a small panel: one textarea and one Ask
 * button. Ask posts only the question to the side-question listener of the
 * wait (engine/btw_listener.py) and shows the answer in the panel. It never
 * touches the lavish queue: queued marks and notes stay queued. The page
 * holds the listener port and token; without them the control is absent.
 */
(function () {
  var holder = document.querySelector('[data-afkv2-btw-port]');
  if (!holder || !document.body) return;
  var url = 'http://127.0.0.1:' + holder.getAttribute('data-afkv2-btw-port') + '/btw';
  var token = holder.getAttribute('data-afkv2-btw-token');
  var NO_WAIT = 'No wait is running for this page, so nobody can answer. Ask in the agent\'s chat.';

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
  hint.textContent = 'Ask sends only this question. Your marks and notes stay queued for Send.';
  var row = document.createElement('div');
  var ask = document.createElement('button');
  ask.type = 'button';
  ask.id = 'afkv2-btw-ask';
  ask.textContent = 'Ask';
  var status = document.createElement('output');
  status.className = 'afkv2-btw-status';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  var answer = document.createElement('div');
  answer.id = 'afkv2-btw-answer';
  answer.hidden = true;
  row.appendChild(status);
  row.appendChild(ask);
  panel.appendChild(question);
  panel.appendChild(hint);
  panel.appendChild(row);
  panel.appendChild(answer);
  var open = document.createElement('button');
  open.type = 'button';
  open.id = 'afkv2-btw-open';
  open.textContent = 'btw?';
  open.title = 'Ask a side question. The agent answers it here.';
  host.appendChild(panel);
  host.appendChild(open);
  document.body.appendChild(host);

  open.addEventListener('click', function () {
    panel.hidden = !panel.hidden;
    if (!panel.hidden) question.focus();
  });

  function show(text) {
    answer.textContent = text;
    answer.hidden = false;
  }

  function send() {
    var text = question.value.trim();
    if (!text || ask.disabled) return;
    ask.disabled = true;
    status.textContent = 'Asking...';
    /* text/plain keeps this a simple request: the browser sends no preflight. */
    fetch(url, { method: 'POST', headers: { 'Content-Type': 'text/plain' },
                 body: JSON.stringify({ token: token, question: text }) })
      .then(function (response) { return response.json(); })
      .then(function (reply) {
        status.textContent = '';
        show('btw: ' + text + '\n\n' + reply.answer);
        if (reply.status !== 'refused') question.value = '';
      }, function () {
        status.textContent = '';
        show(NO_WAIT);
      })
      .then(function () { ask.disabled = false; });
  }
  ask.addEventListener('click', send);
  question.addEventListener('keydown', function (event) {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); send(); }
  });
})();
