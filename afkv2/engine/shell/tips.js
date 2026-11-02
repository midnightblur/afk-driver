(function () {
  var DICT_ID = 'afkv2-tips-dict';
  var el = document.getElementById(DICT_ID);
  var dict; try { dict = JSON.parse(el.textContent); } catch (e) { return; }
  if (!Object.keys(dict).length) return;
  var ciMap = {}, keys, re;
  var esc = function (s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); };
  function rebuild() {
    keys = Object.keys(dict).sort(function (a, b) { return b.length - a.length; });
    keys.forEach(function (k) { if (k === k.toLowerCase()) ciMap[k] = dict[k]; });
    re = new RegExp('(?<![\\w-])(?:' + keys.map(esc).join('|') + ')(?:e?s)?(?!\\w)', 'gi');
  }
  rebuild();

  function lookup(s) {
    if (Object.prototype.hasOwnProperty.call(dict, s)) return dict[s];
    var lower = s.toLowerCase();
    return Object.prototype.hasOwnProperty.call(ciMap, lower) ? ciMap[lower] : null;
  }
  // The wrap regex admits a plural tail; resolve "MRs"/"classes" to their
  // singular key under the same case rules.
  function tipFor(matched) {
    var tip = lookup(matched);
    if (tip === null && matched.length > 2 && /s$/i.test(matched)) {
      tip = lookup(matched.slice(0, -1));
      if (tip === null && /es$/i.test(matched)) tip = lookup(matched.slice(0, -2));
    }
    return tip;
  }

  function wrap(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (!n.nodeValue || n.nodeValue.length > 50000 || !re.test(n.nodeValue)) return NodeFilter.FILTER_REJECT;
        re.lastIndex = 0;
        var p = n.parentElement;
        if (!p || p.closest('script,style,noscript,textarea,.afkv2-tip,#afkv2-tip-box,#afkv2-nav,#afkv2-jump')) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var nodes = [], n;
    while ((n = walker.nextNode())) nodes.push(n);
    nodes.forEach(function (node) {
      var text = node.nodeValue, frag = document.createDocumentFragment(), last = 0, m;
      re.lastIndex = 0;
      while ((m = re.exec(text))) {
        var tip = tipFor(m[0]);
        if (tip === null) continue;
        frag.appendChild(document.createTextNode(text.slice(last, m.index)));
        var span = document.createElement('span');
        span.className = 'afkv2-tip';
        span.setAttribute('data-afkv2-tip', tip);
        span.textContent = m[0];
        frag.appendChild(span);
        last = m.index + m[0].length;
      }
      if (last === 0) return;
      frag.appendChild(document.createTextNode(text.slice(last)));
      node.parentNode.replaceChild(frag, node);
    });
  }

  // Author-side tooltips (item ids etc.): promote title=/data-tip into the same UI.
  function promote(root) {
    root.querySelectorAll('[title],[data-tip]').forEach(function (elx) {
      if (elx.id === 'afkv2-tip-box') return;
      var t = elx.getAttribute('data-tip') || elx.getAttribute('title');
      if (!t) return;
      elx.setAttribute('data-afkv2-tip', t);
      elx.removeAttribute('title');
      if (!elx.hasAttribute('data-lavish-action')) elx.classList.add('afkv2-tip');
    });
  }

  // An id tipped once serves every later bare occurrence: single-token authored tips join the dictionary.
  function harvest(root) {
    var dirty = false;
    root.querySelectorAll('[data-afkv2-tip]').forEach(function (elx) {
      if (elx.closest('#afkv2-tip-box,#afkv2-nav')) return;
      var token = (elx.textContent || '').trim();
      if (!/^[A-Za-z][\w.-]{0,23}$/.test(token)) return;
      if (Object.prototype.hasOwnProperty.call(dict, token)) return;
      dict[token] = elx.getAttribute('data-afkv2-tip');
      dirty = true;
    });
    if (dirty) rebuild();
  }

  var box;
  function ensureBox() {
    if (!box) { box = document.createElement('div'); box.id = 'afkv2-tip-box'; document.body.appendChild(box); }
    return box;
  }
  document.addEventListener('mouseover', function (e) {
    var t = e.target && e.target.closest && e.target.closest('[data-afkv2-tip]');
    if (!t) { if (box) box.style.opacity = '0'; return; }
    var b = ensureBox();
    b.textContent = t.getAttribute('data-afkv2-tip');
    var r = t.getBoundingClientRect(), bw = b.offsetWidth, bh = b.offsetHeight;
    var x = Math.max(6, Math.min(r.left, window.innerWidth - bw - 6));
    var y = r.top - bh - 8;
    if (y < 6) y = r.bottom + 8;
    b.style.left = x + 'px'; b.style.top = y + 'px'; b.style.opacity = '1';
  });
  window.addEventListener('scroll', function () { if (box) box.style.opacity = '0'; }, true);

  var mo;
  function scan() {
    if (mo) mo.disconnect();
    if (navRefresh) navRefresh();
    promote(document.body);
    harvest(document.body);
    wrap(document.body);
    if (mo) mo.observe(document.body, { childList: true, subtree: true });
  }

  // Sticky section rail, collapsed settled cards, jump-to-current control, built from data-afkv2-item,
  // data-afkv2-state and data-afkv2-fresh. A page without that markup gets no chrome.
  var COLLAPSED = 'afkv2-collapsed', MINIMIZED = 'afkv2-min';
  var navRefresh = null;
  function navChrome() {
    if (document.getElementById('afkv2-nav')) return;
    if (!document.querySelector('[data-afkv2-item]')) return;
    var LS = 'afkv2-nav:' + location.pathname;
    var store = {};
    try { store = JSON.parse(localStorage.getItem(LS) || '{}') || {}; } catch (e) {}
    function save() { try { localStorage.setItem(LS, JSON.stringify(store)); } catch (e) {} }
    function items() { return [].slice.call(document.querySelectorAll('[data-afkv2-item]')); }
    function st(el) {
      var s = el.getAttribute('data-afkv2-state');
      return s === 'current' || s === 'settled' || s === 'blocked' ? s : 'open';
    }
    function label(el) {
      var h = el.firstElementChild;
      var raw = (h && h.textContent) || el.getAttribute('data-afkv2-item') || '';
      var t = raw.replace(/\s+/g, ' ').trim();
      return t.length > 64 ? t.slice(0, 61) + '…' : t;
    }
    function setCollapsed(el, on) {
      if (st(el) === 'current') on = false;
      el.classList.toggle('afkv2-collapsed', on);
      var h = el.firstElementChild;
      if (h && st(el) !== 'current') { h.classList.add('afkv2-caret'); h.classList.toggle('afkv2-open', !on); }
    }
    function applyDefaults() {
      items().forEach(function (el) {
        // A table row never folds: folding would leave a one-cell row in a wider table.
        if (el.tagName === 'TR') return;
        var id = el.getAttribute('data-afkv2-item'), s = st(el);
        if (s === 'current') { setCollapsed(el, false); return; }
        if (el.hasAttribute('data-afkv2-nav-done')) return;
        el.setAttribute('data-afkv2-nav-done', '1');
        var expanded = Object.prototype.hasOwnProperty.call(store, id) ? !!store[id] : s !== 'settled';
        setCollapsed(el, !expanded);
        var h = el.firstElementChild;
        if (h) {
          h.setAttribute('data-lavish-action', 'afkv2-collapse');
          h.addEventListener('click', function () {
            var wasCollapsed = el.classList.contains(COLLAPSED);
            setCollapsed(el, !wasCollapsed);
            store[id] = wasCollapsed ? 1 : 0; save();
          });
        }
      });
    }
    function goTo(el) {
      setCollapsed(el, false);
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      el.classList.add('afkv2-flash');
      setTimeout(function () { el.classList.remove('afkv2-flash'); }, 1600);
    }
    var nav = document.createElement('div');
    nav.id = 'afkv2-nav';
    nav.setAttribute('data-lavish-ui', 'afkv2-nav');
    nav.setAttribute('data-lavish-action', 'afkv2-nav');
    nav.innerHTML = '<div id="afkv2-nav-head" role="button" tabindex="0"><b>On this page</b><span>–</span></div><div id="afkv2-nav-list"></div>';
    document.body.appendChild(nav);
    nav.addEventListener('keydown', function (e) {
      if ((e.key === 'Enter' || e.key === ' ') && e.target && e.target.click) { e.preventDefault(); e.target.click(); }
    });
    if (store['__min']) nav.classList.add('afkv2-min');
    nav.querySelector('#afkv2-nav-head').addEventListener('click', function () {
      nav.classList.toggle('afkv2-min');
      store['__min'] = nav.classList.contains(MINIMIZED) ? 1 : 0; save();
    });
    var GROUPS = [['current', 'Now'], ['open', 'Open'], ['blocked', 'Blocked'], ['settled', 'Settled']];
    // Unforced refreshes skip when the item set is unchanged, so a mutation does not replace a rail about to be clicked.
    var navSig = null;
    function rebuildNav(force) {
      var els = items();
      var sig = els.map(function (el) {
        return el.getAttribute('data-afkv2-item') + '|' + st(el) + '|' +
          (el.hasAttribute('data-afkv2-fresh') ? 1 : 0) + '|' + label(el);
      }).join(';');
      if (!force && sig === navSig) return;
      navSig = sig;
      applyDefaults();
      var list = nav.querySelector('#afkv2-nav-list');
      list.textContent = '';
      GROUPS.forEach(function (g) {
        var members = els.filter(function (el) { return st(el) === g[0]; });
        if (!members.length) return;
        var gk = '__g:' + g[0];
        var open = Object.prototype.hasOwnProperty.call(store, gk) ? !!store[gk] : g[0] !== 'settled';
        var head = document.createElement('div');
        head.className = 'afkv2-nav-g';
        head.textContent = (open ? '▾ ' : '▸ ') + g[1] + (g[0] === 'current' ? '' : ' (' + members.length + ')');
        head.setAttribute('data-lavish-action', 'afkv2-nav');
        head.setAttribute('role', 'button');
        head.setAttribute('tabindex', '0');
        head.addEventListener('click', function () { store[gk] = open ? 0 : 1; save(); rebuildNav(true); });
        list.appendChild(head);
        if (!open) return;
        members.forEach(function (el) {
          var row = document.createElement('div');
          row.className = 'afkv2-nav-row' + (g[0] === 'current' ? ' afkv2-cur' : '');
          row.setAttribute('data-lavish-action', 'afkv2-nav');
          row.setAttribute('role', 'button');
          row.setAttribute('tabindex', '0');
          if (el.hasAttribute('data-afkv2-fresh')) {
            var dot = document.createElement('span');
            dot.className = 'afkv2-dot';
            dot.setAttribute('data-afkv2-tip', 'Changed by the round just applied');
            row.appendChild(dot);
          }
          row.appendChild(document.createTextNode(label(el)));
          row.addEventListener('click', function () { goTo(el); });
          list.appendChild(row);
        });
      });
    }
    function currentAnswerSurface() {
      var current = document.querySelector('[data-afkv2-state="current"]');
      if (!current) return null;
      return current.closest('[data-afkv2-answer-form="1"]') || current;
    }
    var jump = document.createElement('button');
    jump.type = 'button';
    jump.id = 'afkv2-jump';
    jump.setAttribute('data-lavish-action', 'afkv2-nav');
    jump.textContent = '↑ Current question';
    jump.addEventListener('click', function () {
      var cur = currentAnswerSurface();
      if (cur) goTo(cur);
    });
    document.body.appendChild(jump);
    var cur = currentAnswerSurface();
    if (cur && 'IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) {
        jump.style.display = entries[0].isIntersecting ? 'none' : 'block';
      }).observe(cur);
    }
    rebuildNav(true);
    navRefresh = function () { rebuildNav(false); };
  }

  function start() {
    var pending;
    mo = new MutationObserver(function (recs) {
      var ours = recs.every(function (r) {
        return (box && (r.target === box || box.contains(r.target))) ||
               (r.target && r.target.closest && r.target.closest('#afkv2-nav,#afkv2-jump'));
      });
      if (ours) return;
      clearTimeout(pending); pending = setTimeout(scan, 300);
    });
    navChrome();
    scan();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
