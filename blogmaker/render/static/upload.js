// 업로드 폼: GitHub Contents API로 requests/<ID>/ 에 zip과 request.json을 올리고 진행 상황을 확인한다.
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var KEY = 'culture-blog-token';
  var API = 'https://api.github.com';

  function store(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch (e) {} }
  function load(k) { try { return localStorage.getItem(k) || ''; } catch (e) { return ''; } }

  // 저장소 기본값: 빌드 시 넣은 값 → Pages 주소(계정.github.io/저장소)에서 추정
  if (!$('owner').value && location.hostname.endsWith('.github.io')) $('owner').value = location.hostname.split('.')[0];
  if (!$('repo').value && location.hostname.endsWith('.github.io')) $('repo').value = location.pathname.split('/')[1] || '';
  $('token').value = load(KEY);
  function tokState() { $('tokstate').textContent = $('token').value ? '· 토큰 저장됨' : '· 토큰 필요'; }
  tokState();
  if (!$('token').value) $('settings').open = true;
  $('forget').onclick = function () { store(KEY, null); $('token').value = ''; tokState(); };

  var steps = [];
  function step(text, cls) {
    var p = document.createElement('div');
    p.className = 'step ' + (cls || 'on'); p.textContent = text;
    $('status').appendChild(p); steps.push(p); return p;
  }
  function mark(p, cls, text) { p.className = 'step ' + cls; if (text) p.textContent = text; }

  function gh(path, opt) {
    opt = opt || {};
    opt.headers = Object.assign({
      'Authorization': 'Bearer ' + $('token').value.trim(),
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    }, opt.headers || {});
    return fetch(API + path, opt).then(function (r) {
      if (r.status === 404) return null;
      if (!r.ok) return r.text().then(function (t) { throw new Error(r.status + ' ' + t.slice(0, 200)); });
      return r.json();
    });
  }

  function b64File(file) {
    return new Promise(function (res, rej) {
      var fr = new FileReader();
      fr.onload = function () { res(String(fr.result).split(',')[1]); };
      fr.onerror = rej; fr.readAsDataURL(file);
    });
  }
  function b64Text(s) { return btoa(unescape(encodeURIComponent(s))); }

  function pid(url) {
    var m = url.match(/products\/(\d+)/) || url.match(/goods\/(\d+)/) || url.match(/GoodsCode=(\d+)/i);
    return m ? m[1] : 'x';
  }
  function stamp() {
    var d = new Date(Date.now() + 9 * 3600 * 1000).toISOString();   // KST
    return d.slice(0, 10).replace(/-/g, '') + '-' + d.slice(11, 19).replace(/:/g, '');
  }
  var sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };

  $('f').addEventListener('submit', async function (ev) {
    ev.preventDefault();
    var owner = $('owner').value.trim(), repo = $('repo').value.trim(), token = $('token').value.trim();
    var url = $('url').value.trim(), file = $('zip').files[0];
    if (!owner || !repo || !token) { $('settings').open = true; alert('GitHub 계정·저장소·토큰을 입력해 주세요.'); return; }
    if (file.size > 90 * 1024 * 1024) { alert('파일이 너무 큽니다 (90MB 이하).'); return; }
    store(KEY, token); tokState();

    $('go').disabled = true; $('statusbox').hidden = false; $('status').innerHTML = '';
    var id = stamp() + '-' + pid(url);
    var base = '/repos/' + owner + '/' + repo + '/contents/';
    var ext = (file.name.match(/\.[^.]+$/) || ['.zip'])[0].toLowerCase();

    try {
      var s1 = step('1. 상세 이미지 올리는 중…');
      await gh(base + 'requests/' + id + '/upload' + ext, { method: 'PUT',
        body: JSON.stringify({ message: 'upload: ' + id, content: await b64File(file) }) });
      mark(s1, 'ok', '1. 상세 이미지 업로드 완료');

      var s2 = step('2. 요청 등록 중…');
      var req = { url: url, created_at: new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 19) + '+09:00' };
      await gh(base + 'requests/' + id + '/request.json', { method: 'PUT',
        body: JSON.stringify({ message: 'request: ' + id, content: b64Text(JSON.stringify(req, null, 1)) }) });
      mark(s2, 'ok', '2. 요청 등록 완료 → GitHub Actions 실행 대기');

      var s3 = step('3. 글 작성 중… (보통 1~3분)');
      try {
        var runs = await gh('/repos/' + owner + '/' + repo + '/actions/runs?per_page=1');
        if (runs && runs.workflow_runs && runs.workflow_runs[0]) { $('runlink').href = runs.workflow_runs[0].html_url; $('runlink').hidden = false; }
      } catch (e) {}

      var done = null;
      for (var i = 0; i < 60 && !done; i++) {      // 최대 약 15분
        await sleep(15000);
        var ok = await gh(base + 'content/posts/' + id + '/post.json');
        if (ok) { done = 'ok'; break; }
        var err = await gh(base + 'content/posts/' + id + '/error.json');
        if (err) { done = JSON.parse(decodeURIComponent(escape(atob(err.content.replace(/\n/g, ''))))).error; break; }
      }
      if (done !== 'ok') { mark(s3, 'err', '3. 실패: ' + (done || '시간 초과 — Actions 화면에서 확인해 주세요')); return; }
      mark(s3, 'ok', '3. 글 작성 완료');

      var s4 = step('4. 사이트 배포 중…');
      var page = location.href.replace(/upload\.html.*$/, '') + 'posts/' + id + '/index.html';
      for (var j = 0; j < 40; j++) {
        await sleep(10000);
        var r = await fetch(page, { method: 'HEAD', cache: 'no-store' }).catch(function () { return null; });
        if (r && r.ok) break;
      }
      mark(s4, 'ok', '4. 배포 완료');
      var a = document.createElement('a'); a.href = page; a.className = 'copy'; a.textContent = '만든 초안 열기 →';
      a.style.display = 'inline-block'; a.style.marginTop = '10px'; $('status').appendChild(a);
    } catch (e) {
      step('오류: ' + e.message + ' (토큰 권한·저장소 이름을 확인해 주세요)', 'err');
    } finally {
      $('go').disabled = false;
    }
  });
})();
