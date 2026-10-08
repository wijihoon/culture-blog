// 제목·본문·태그 복사 (본문은 서식 포함)
document.querySelectorAll('button.copy[data-target]').forEach(function (btn) {
  btn.addEventListener('click', async function () {
    var el = document.getElementById(btn.dataset.target);
    var html = el.innerHTML, text = el.innerText;
    try {
      if (btn.dataset.target === 'post' && window.ClipboardItem) {
        await navigator.clipboard.write([new ClipboardItem({
          'text/html': new Blob([html], { type: 'text/html' }),
          'text/plain': new Blob([text], { type: 'text/plain' })
        })]);
      } else {
        await navigator.clipboard.writeText(text.trim());
      }
    } catch (e) {
      var r = document.createRange(); r.selectNodeContents(el);
      var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
      document.execCommand('copy'); s.removeAllRanges();
    }
    var old = btn.textContent;
    btn.textContent = '복사됨'; btn.classList.add('done');
    setTimeout(function () { btn.textContent = old; btn.classList.remove('done'); }, 1500);
  });
});
