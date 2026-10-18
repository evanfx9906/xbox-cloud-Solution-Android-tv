/* Xbox Lab (lean, v11). Runs at document start on play.xbox.com / www.xbox.com.
 * What it does (all in the page, nothing leaves the phone):
 *  1. Market: rewrites the market the page sends (market=GR, locale=xx-GR, x-xbl-market, JSON body market
 *     fields) to the market chosen in the app's Server Region setting.
 *  2. Streaming servers (*.gssv-play-prod.xboxlive.com) and the page's own client-IP headers get the
 *     chosen region's example client IP (with a safe fallback if the server refuses the extra header).
 *  3. Experiment answer: default offering CLOUDGAMING is changed to XGPUWEB (kept from the working lab build).
 *  4. Aspect ratio on the stream screen (16:9 / 18:9 / Stretch) via a CSS scale on the video element.
 * Logging is minimal: a few short lines (addresses without ids, never tokens or page text). */
(function () {
  try {
    if (window.__labLean) return;
    window.__labLean = true;
    var isTop = (window === window.top);
    var T0 = Date.now(), buf = [], counts = {}, sent = 0, MAX_EVENTS = 80;

    function maskPiece(s) {
      s = String(s);
      s = s.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/ig, '{guid}');
      s = s.replace(/[0-9a-f]{16,}/ig, '{hex}');
      s = s.replace(/[0-9]{6,}/g, '{num}');
      return s.length > 40 ? '{long}' : s;
    }
    function maskPath(p) { return String(p || '').split('/').map(maskPiece).join('/'); }
    function scrub(t) { return String(t == null ? '' : t).replace(/https?:\/\/\S+/g, '{url}').slice(0, 120); }
    function emit(kind, detail) {
      try {
        var key = kind + '|' + detail;
        counts[key] = (counts[key] || 0) + 1;
        if (counts[key] > 1 || sent >= MAX_EVENTS) return;
        sent++;
        buf.push({ t: Date.now() - T0, k: kind, d: detail });
      } catch (e) { }
    }
    function flush() {
      try { if (buf.length) console.log('[LABPROBE] ' + JSON.stringify(buf.splice(0, buf.length))); } catch (e) { }
    }
    setInterval(flush, 8000);
    window.addEventListener('pagehide', flush);

    // ---------- market / client-IP / streaming-server rewriting ----------
    var BYPASS_IPS = { US: '143.244.47.65', BR: '169.150.198.66', KR: '121.125.60.151', JP: '138.199.21.239',
                       PL: '45.134.212.66', ES: '80.58.61.250', GB: '62.24.134.1', FR: '212.27.40.240' };
    var realMarket = null;
    var REWRITE_HOSTS = /(xboxservices\.com|xboxlive\.com|gamepass\.com)$/i;
    var SKIP_HOSTS = /^(user|xsts|device|title)\.auth\.xboxlive\.com$|^login\./i;
    var MARKET_PARAMS = /^(market|mkt|country|countrycode|clientcountry)$/i;
    var LOCALE_PARAMS = /^(locale|clientlocale)$/i;
    var IP_HEADERS = ['forwarded', 'clientip', 'x-forwarded-for', 'x-client-ip'];

    function targetMarket() {
      try {
        var m = window.LabBridge && window.LabBridge.market && window.LabBridge.market();
        if (m && /^[A-Z]{2}$/.test(m)) return m;
      } catch (e) { }
      return 'ES';
    }
    function rewritableHost(urlStr) {
      try { var h = new URL(String(urlStr), location.href).hostname; return REWRITE_HOSTS.test(h) && !SKIP_HOSTS.test(h); }
      catch (e) { return false; }
    }
    function rewriteUrlString(s, M) {
      var out = { url: s, changed: false, note: '' };
      try {
        var a = new URL(String(s), location.href);
        if (!REWRITE_HOSTS.test(a.hostname) || SKIP_HOSTS.test(a.hostname)) return out;
        var pairs = [];
        a.searchParams.forEach(function (v, k) { pairs.push([k, v]); });
        pairs.forEach(function (kv) { if (MARKET_PARAMS.test(kv[0]) && /^[A-Za-z]{2}$/.test(kv[1]) && !realMarket) realMarket = kv[1].toUpperCase(); });
        var notes = [];
        pairs.forEach(function (kv) {
          var k = kv[0], v = kv[1];
          if (MARKET_PARAMS.test(k) && /^[A-Za-z]{2}$/.test(v)) {
            if (v.toUpperCase() !== M) { a.searchParams.set(k, M); notes.push(k + ':' + v.toUpperCase() + '>' + M); }
          } else if (LOCALE_PARAMS.test(k)) {
            var mm = /^([A-Za-z]{2,3})-([A-Za-z]{2})$/.exec(v);
            if (mm && realMarket && realMarket !== M && mm[2].toUpperCase() === realMarket) {
              var nv = mm[1].toLowerCase() + '-' + M; a.searchParams.set(k, nv); notes.push(k + ':' + v + '>' + nv);
            }
          }
        });
        if (notes.length) { out.url = a.toString(); out.changed = true; out.note = notes.join(','); }
      } catch (e) { }
      return out;
    }
    function swapIp(name, value, ip) {
      var v = String(value), v4 = /\b\d{1,3}(\.\d{1,3}){3}\b/;
      if (v4.test(v)) return v.replace(v4, ip);
      if (/:[0-9a-f]*:/i.test(v)) return name === 'forwarded' ? 'for=' + ip : ip;
      return null;
    }
    function rewriteHeaders(src, M, host) {
      try {
        var hh = new Headers(src || undefined), notes = [], changed = false;
        var cur = hh.get('x-xbl-market');
        if (cur !== null) {
          if (!realMarket && /^[A-Za-z]{2}$/.test(cur)) realMarket = cur.toUpperCase();
          if (cur.toUpperCase() !== M) { hh.set('x-xbl-market', M); notes.push('x-xbl-market:' + cur.toUpperCase() + '>' + M); changed = true; }
        }
        var ip = BYPASS_IPS[M] || BYPASS_IPS.US;
        IP_HEADERS.forEach(function (nm) {
          var v = hh.get(nm); if (v === null) return;
          var nv = swapIp(nm, v, ip);
          if (nv !== null && nv !== v) { hh.set(nm, nv); notes.push(nm + ':client-ip>' + M + '-ip'); changed = true; }
        });
        var gssv = !!host && /\.gssv-play-prod\.xboxlive\.com$/i.test(host);
        if (gssv && hh.get('x-forwarded-for') === null) { hh.set('x-forwarded-for', ip); notes.push('gssv:x-forwarded-for added'); changed = true; }
        return changed ? { headers: hh, note: notes.join(','), gssv: gssv } : null;
      } catch (e) { return null; }
    }
    function rewriteBodyMarket(body, M) {
      try {
        if (typeof body !== 'string' || (body.charAt(0) !== '{' && body.charAt(0) !== '[')) return null;
        var obj = JSON.parse(body), notes = [];
        (function walk(o, d) {
          if (!o || typeof o !== 'object' || d > 4) return;
          Object.keys(o).forEach(function (k) {
            var v = o[k];
            if (/^(market|country|countrycode|clientcountry)$/i.test(k) && typeof v === 'string' && /^[A-Za-z]{2}$/.test(v)) {
              if (v.toUpperCase() !== M) { notes.push(k + ':' + v.toUpperCase() + '>' + M); o[k] = (v === v.toLowerCase()) ? M.toLowerCase() : M; }
            } else walk(v, d + 1);
          });
        })(obj, 0);
        return notes.length ? { body: JSON.stringify(obj), note: 'body{' + notes.join(',') + '}' } : null;
      } catch (e) { return null; }
    }
    var EXP_URL = /emerald\.xboxservices\.com\/xboxcomfd\/experimentation/;
    function patchExperimentation(r) {
      try {
        if (!r || !r.ok) return r;
        return r.clone().json().then(function (j) {
          var changes = 0;
          (function walk(o, d) {
            if (!o || typeof o !== 'object' || d > 9) return;
            Object.keys(o).forEach(function (k) {
              var v = o[k];
              if (typeof v === 'string' && v.length < 4000 && /cloudgaming/i.test(v)) {
                o[k] = v.replace(/CLOUDGAMING/g, 'XGPUWEB').replace(/cloudgaming/g, 'xgpuweb').replace(/CloudGaming/g, 'XgpuWeb'); changes++;
              } else if (v && typeof v === 'object') walk(v, d + 1);
            });
          })(j, 0);
          emit('exp_patch', changes ? 'changed ' + changes + ' value(s)' : 'nothing to change');
          if (!changes) return r;
          var hdrs = new Headers(r.headers); hdrs.delete('content-length'); hdrs.delete('content-encoding');
          var nr = new Response(JSON.stringify(j), { status: r.status, statusText: r.statusText, headers: hdrs });
          try { Object.defineProperty(nr, 'url', { value: r.url }); } catch (e) { }
          return nr;
        }, function () { return r; });
      } catch (e) { return r; }
    }
    function planRewrite(input, init) {
      var M = targetMarket();
      var isReq = (typeof Request === 'function') && (input instanceof Request);
      var urlStr = isReq ? input.url : String(input);
      if (!rewritableHost(urlStr)) return null;
      var u = rewriteUrlString(urlStr, M);
      var hostName = '';
      try { hostName = new URL(urlStr, location.href).hostname; } catch (e) { }
      var hdrSrc = (init && init.headers) ? init.headers : (isReq ? input.headers : null);
      var h = rewriteHeaders(hdrSrc, M, hostName);
      var bm = (!isReq && init && typeof init.body === 'string') ? rewriteBodyMarket(init.body, M) : null;
      if (!u.changed && !h && !bm) return null;
      var note = [u.note, h && h.note, bm && bm.note].filter(Boolean).join(' ');
      emit('rewrite', hostName + maskPath(new URL(urlStr, location.href).pathname) + ' ' + note + (isReq ? ' (Request object)' : ''));
      var gssvAdded = !!(h && h.gssv && /gssv:/.test(h.note || ''));
      if (!isReq) {
        var ni = Object.assign({}, init || {});
        if (h && h.headers) ni.headers = h.headers;
        if (bm) ni.body = bm.body;
        return { gssvAdded: gssvAdded, promise: Promise.resolve([u.changed ? u.url : input, ni]) };
      }
      var method = String(input.method || 'GET').toUpperCase();
      var bodyP = (method === 'GET' || method === 'HEAD') ? Promise.resolve(undefined) : input.clone().arrayBuffer();
      return {
        gssvAdded: gssvAdded,
        promise: bodyP.then(function (buf2) {
          var base = { method: input.method, headers: input.headers, body: buf2, mode: input.mode, credentials: input.credentials,
                       cache: input.cache, redirect: input.redirect, referrer: input.referrer, referrerPolicy: input.referrerPolicy,
                       integrity: input.integrity, keepalive: input.keepalive, signal: input.signal };
          var merged = Object.assign(base, init || {});
          if (h) merged.headers = h.headers;
          return [new Request(u.changed ? u.url : input.url, merged), undefined];
        })
      };
    }

    var ofetch = window.fetch;
    function loggedFetch(input, init) {
      var rawUrl = '';
      try { rawUrl = String((typeof input === 'string') ? input : (input && input.url)); } catch (e) { }
      var p = ofetch.apply(this, arguments);
      if (EXP_URL.test(rawUrl)) return p.then(patchExperimentation);
      return p;
    }
    if (ofetch) {
      window.fetch = function (input, init) {
        var self = this, plan = null;
        try { plan = planRewrite(input, init); } catch (e) { plan = null; }
        if (!plan) return loggedFetch.call(self, input, init);
        return plan.promise.then(
          function (args) {
            var q = loggedFetch.call(self, args[0], args[1]);
            if (plan.gssvAdded) return q.catch(function (e) { emit('gssv_header_blocked', scrub(e && e.name)); return loggedFetch.call(self, input, init); });
            return q;
          },
          function (err) { emit('rewrite_failed', scrub(err && err.name)); return loggedFetch.call(self, input, init); }
        );
      };
    }
    if (isTop) emit('market_target', targetMarket() + ' bridge=' + (window.LabBridge ? 'yes' : 'no'));

    // ---------- aspect ratio on the stream screen ----------
    // modes: 0 = 16:9 (site default), 1 = 18:9, 2 = Stretch (full screen)
    var LABELS = ['Aspect ratio: 16:9', 'Aspect ratio: 18:9', 'Aspect ratio: Stretch (full screen)'];
    var aspectMode = 0, aspectEl = null;
    try { var sv = parseInt(localStorage.getItem('labAspectMode'), 10); if (sv >= 0 && sv <= 2) aspectMode = sv; } catch (e) { }
    function onStreamScreen() { return /^\/stream\//.test(location.pathname); }
    function biggestMedia() {
      var best = null, area = 0;
      Array.prototype.forEach.call(document.querySelectorAll('video, canvas'), function (el) {
        var r = el.getBoundingClientRect(), a = r.width * r.height;
        if (r.width > 160 && r.height > 90 && a > area) { area = a; best = el; }
      });
      return best;
    }
    function clearAspect(el) { try { if (el) el.style.removeProperty('scale'); } catch (e) { } }
    function applyAspect() {
      try {
        if (!onStreamScreen()) { clearAspect(aspectEl); aspectEl = null; return; }
        var el = biggestMedia();
        if (!el) return;
        if (aspectEl && aspectEl !== el) clearAspect(aspectEl);
        aspectEl = el;
        var W = window.innerWidth, H = window.innerHeight;
        var base = Math.min(W, H * 16 / 9);
        var target = aspectMode === 0 ? base : (aspectMode === 1 ? Math.min(W, H * 2) : W);
        var f = base > 0 ? target / base : 1;
        if (f > 1.001) el.style.setProperty('scale', f.toFixed(4) + ' 1', 'important');
        else el.style.removeProperty('scale');
      } catch (e) { }
    }
    window.__labAspectLabel = function () { return LABELS[aspectMode]; };
    window.__labAspectCycle = function () {
      aspectMode = (aspectMode + 1) % 3;
      try { localStorage.setItem('labAspectMode', String(aspectMode)); } catch (e) { }
      applyAspect();
      return LABELS[aspectMode];
    };
    if (isTop) {
      setInterval(applyAspect, 1000);
      window.addEventListener('resize', applyAspect);
    }
  } catch (e) { }
})();
