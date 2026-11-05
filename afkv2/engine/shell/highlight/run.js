/* Colours each code block and diff line that the engine marked with a language highlight.js knows.
 * An unknown language, or a block with no mark, stays uncoloured. The text is never changed. */
(function () {
  if (typeof hljs === 'undefined') return;
  var blocks = document.querySelectorAll('code[data-afkv2-lang]');
  for (var i = 0; i < blocks.length; i++) {
    var language = blocks[i].getAttribute('data-afkv2-lang');
    if (!hljs.getLanguage(language)) continue;
    blocks[i].innerHTML = hljs.highlight(blocks[i].textContent, { language: language, ignoreIllegals: true }).value;
  }
})();
