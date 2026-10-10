/* Xbox Lab probe v4 (diagnostics + market experiment + offering test). Runs at document start on play.xbox.com / www.xbox.com.
 * Records WHAT the page does, never what it contains: no cookies, headers, bodies, tokens, query
 * strings, fragments, page text or account names. Addresses are reduced to host + path with
 * id-like path pieces masked. Output goes to console.log("[LABPROBE] ...") and the app writes it
 * to its debug log.
 * EXPERIMENT (v3): rewrites the market the page sends (market=GR, locale=xx-GR, x-xbl-market header) to
 * the market chosen in the app's Server Region setting, to test whether the server trusts it. */
(function () {
  try {
    if (window.__labProbe) return;
    window.__labProbe = true;

    var T0 = Date.now();
    var isTop = (window === window.top);
    var buf = [];
    var counts = {};
    var sent = 0;
    var MAX_EVENTS = 500;

    function maskPiece(s) {
      s = String(s);
      s = s.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/ig, '{guid}');
      s = s.replace(/[0-9a-f]{16,}/ig, '{hex}');
      s = s.replace(/[0-9]{6,}/g, '{num}');
      if (s.length > 40) return '{long}';
      return s;
    }
    function maskPath(p) {
      return String(p || '').split('/').map(maskPiece).join('/');
    }

    function safeUrl(u) {
      try {
        var s = String(u);
        if (/^blob:/i.test(s)) return 'blob:';
        if (/^data:/i.test(s)) return 'data:';
        var a = new URL(s, location.href);
        return a.protocol + '//' + a.host + maskPath(a.pathname);
      } catch (e) {
        return 'unparsable';
      }
    }

    var VALUE_PARAMS = /^(market|mkt|locale|language|languages|lang|country|countrycode|region|culture|geo|clientlocale|clientcountry|clientlanguage|offering|offerings|offeringid)$/i;
    var seenReq = {};
    function reqDetail(u, init, input) {
      try {
        var s = String(u);
        if (/^(blob|data):/i.test(s)) return null;
        var a = new URL(s, location.href);
        if (!/(xboxservices\.com|xboxlive\.com|gamepass\.com|xbox\.com)$/i.test(a.hostname)) return null;
        var names = [];
        a.searchParams.forEach(function (v, k) {
          if (VALUE_PARAMS.test(k) && /^[A-Za-z0-9_,\-]{1,14}$/.test(v)) names.push(k + '=' + v);
          else names.push(k);
        });
        var hdrs = [];
        var h = (init && init.headers) || (input && input.headers);
        if (h) {
          if (typeof h.forEach === 'function' && !Array.isArray(h)) h.forEach(function (v, k) { hdrs.push(String(k).toLowerCase()); });
          else if (Array.isArray(h)) h.forEach(function (p) { hdrs.push(String(p[0]).toLowerCase()); });
          else Object.keys(h).forEach(function (k) { hdrs.push(k.toLowerCase()); });
        }
        var key = a.hostname + maskPath(a.pathname);
        if (seenReq[key]) return null;
        seenReq[key] = 1;
        return 'params[' + names.join(',') + '] headers[' + hdrs.join(',') + ']';
      } catch (e) { return null; }
    }

    var OK_KEYS = /^(id|offering|offerings|offeringid|offeringids|hasaccess|access|allowed|isavailable|tier|subscription|type|name|kind|state|status|market|region|regions|country|countrycode|locale|culture|language|lang|code|availability|reason|message|action|actions|platform|platforms|cloud|isxcloud|xcloud|supported|enabled|available|iscloud|offeringsettings|allowregionselection|isdefaultregion)$/i;
    function maskKey(k) { return maskPiece(k); }
    function scrubValue(v) {
      var t = String(v);
      if (/^https?:\/\//i.test(t)) { try { return new URL(t).host; } catch (e) { return 'url'; } }
      return maskPiece(scrub(t).replace(/[^\s@"]+@[^\s@"]+/g, '{email}')).slice(0, 60);
    }
    function shape(v, depth, key) {
      if (v === null) return 'null';
      var t = typeof v;
      if (t === 'string') return OK_KEYS.test(key || '') ? JSON.stringify(scrubValue(v)) : 'str';
      if (t === 'number' || t === 'boolean') return OK_KEYS.test(key || '') ? String(v) : t;
      if (Array.isArray(v)) {
        var kinds = '';
        if (v.length && /^(actions|sections|layouts|rows|tiles|offerings|items|results|data|value|values)$/i.test(key || '')) {
          kinds = ' kinds=[' + v.slice(0, 12).map(function (e) {
            var x = e && (e.type || e.actionType || e.kind || e.name || e.id || e.offeringId || e.offering);
            return typeof x === 'string' ? scrubValue(x).slice(0, 30) : '?';
          }).join('|') + ']';
        }
        return 'arr[' + v.length + ']' + kinds + ((v.length && depth <= 3) ? '<' + shape(v[0], depth + 1, key) + '>' : '');
      }
      if (t === 'object') {
        if (depth > 3) return '{..}';
        var ks = Object.keys(v);
        return '{' + ks.slice(0, 30).map(function (k) { return maskKey(k) + ':' + shape(v[k], depth + 1, k); }).join(',') + (ks.length > 30 ? ',..' + ks.length : '') + '}';
      }
      return t;
    }
    var SHAPE_URLS = /(xCloudWebHome|\/api\/details\/[^\/]+\/actions|catalog\.gamepass\.com\/sigls\/v3|contentaccess\.exp\.xboxservices\.com\/all\/v1|title\.mgt\.xboxlive\.com\/titles\/default\/endpoints)/;
    var shapeCount = {};
    var OFFER_URL = /contentaccess\.exp\.xboxservices\.com\/all\/v1/;
    function captureOffering(tag, urlStr, r, input, init) {
      try {
        if (!OFFER_URL.test(urlStr)) return false;
        var hsrc = (init && init.headers) ? init.headers : ((typeof Request === 'function' && input instanceof Request) ? input.headers : null);
        var ct = r.headers && r.headers.get ? r.headers.get('content-type') : '';
        r.clone().text().then(function (t) {
          var hash = h32(t);
          emit('offer_baseline', r.status + ' ct=' + scrub(ct) + ' len=' + t.length + ' hash=' + hash + ' ' + describeBody(t));
          offeringTests(urlStr, hsrc, hash);
        }, function () { });
        return true;
      } catch (e) { return false; }
    }
    function captureShape(tag, urlStr, r) {
      try {
        if (!SHAPE_URLS.test(urlStr)) return;
        var k = tag.replace(/\{[a-z]+\}/g, '');
        shapeCount[k] = (shapeCount[k] || 0) + 1;
        if (shapeCount[k] > 4) return;
        r.clone().json().then(function (j) {
          emit('shape', tag.split(' ')[1].replace(/^https?:\/\//, '') + ' => ' + shape(j, 0, '').slice(0, 1800));
        }, function () { });
      } catch (e) { }
    }

    function scrub(text) {
      return String(text == null ? '' : text).replace(/https?:\/\/\S+/g, '{url}').slice(0, 120);
    }

    function emit(kind, detail) {
      try {
        var key = kind + '|' + detail;
        counts[key] = (counts[key] || 0) + 1;
        if (counts[key] > 1) return;
        if (sent >= MAX_EVENTS) return;
        sent++;
        buf.push({ t: Date.now() - T0, top: isTop, k: kind, d: detail });
      } catch (e) { }
    }

    function flush() {
      try {
        if (!buf.length) return;
        var out = buf.splice(0, buf.length);
        console.log('[LABPROBE] ' + JSON.stringify(out));
      } catch (e) { }
    }

    function summary() {
      try {
        var rows = [];
        Object.keys(counts).forEach(function (k) { if (counts[k] > 2) rows.push([k, counts[k]]); });
        rows.sort(function (a, b) { return b[1] - a[1]; });
        if (rows.length) {
          emit('summary', rows.slice(0, 12).map(function (r) { return r[1] + 'x ' + r[0]; }).join(' ;; ') + ' @' + Math.round((Date.now() - T0) / 1000) + 's');
        }
      } catch (e) { }
    }

    setInterval(flush, 2000);
    setInterval(summary, 30000);
    window.addEventListener('pagehide', function () { summary(); flush(); });

    if (isTop) { emit('market_target', targetMarket() + ' bridge=' + (window.LabBridge ? 'yes' : 'no')); }

    var ref = '';
    try { ref = document.referrer ? new URL(document.referrer).host : ''; } catch (e) { }
    emit('doc_start', location.host + maskPath(location.pathname) + ' referrer=' + ref);

    if (isTop) {
      var brands = '';
      try {
        brands = (navigator.userAgentData && navigator.userAgentData.brands || [])
          .map(function (b) { return b.brand + ' ' + b.version; }).join(',');
      } catch (e) { }
      emit('env', JSON.stringify({
        ua: navigator.userAgent, brands: brands,
        mobile: navigator.userAgentData ? navigator.userAgentData.mobile : null,
        w: window.innerWidth, h: window.innerHeight, dpr: window.devicePixelRatio,
        serviceWorkerApi: !!navigator.serviceWorker,
        lang: navigator.language, langs: (navigator.languages || []).join(','),
        tz: (function () { try { return Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e) { return ''; } })()
      }));
    }

    // ---- offering test (v4) ----
    var BYPASS_IPS = { US: '143.244.47.65', BR: '169.150.198.66', KR: '121.125.60.151', JP: '138.199.21.239',
                       PL: '45.134.212.66', ES: '80.58.61.250', GB: '62.24.134.1', FR: '212.27.40.240' };
    function h32(t) {
      var h = 5381;
      for (var i = 0; i < t.length; i++) { h = ((h << 5) + h + t.charCodeAt(i)) | 0; }
      return (h >>> 0).toString(16);
    }
    function describeBody(t) {
      try { return 'json ' + shape(JSON.parse(t), 0, '').slice(0, 1500); } catch (e) { }
      try {
        var m = /^[A-Za-z0-9_-]+\.([A-Za-z0-9_-]+)\.[A-Za-z0-9_-]*$/.exec(String(t).trim());
        if (m) {
          var p = JSON.parse(atob(m[1].replace(/-/g, '+').replace(/_/g, '/')));
          return 'jwt-payload ' + shape(p, 0, '').slice(0, 1500);
        }
      } catch (e) { }
      return 'non-json start=' + String(t).slice(0, 1).replace(/[A-Za-z0-9]/g, 'a');
    }
    var offerTestsDone = false;
    function offeringTests(urlStr, headersSrc, baseHash) {
      if (offerTestsDone) return;
      offerTestsDone = true;
      var M = '';
      try { M = (window.LabBridge && window.LabBridge.market && window.LabBridge.market()) || ''; } catch (e) { }
      var ip = BYPASS_IPS[M] || BYPASS_IPS.ES;
      var variants = [['x-forwarded-for', ip], ['forwarded', 'for=' + ip], ['clientip', ip]];
      function one(v) {
        var h = new Headers(headersSrc || undefined);
        h.set(v[0], v[1]);
        return ofetch.call(window, urlStr, { method: 'GET', headers: h, mode: 'cors' }).then(function (r) {
          return r.text().then(function (t) {
            emit('offer_test', v[0] + ' -> ' + r.status + ' len=' + t.length + ' vsBaseline=' + (h32(t) === baseHash ? 'same' : 'DIFFERENT') + ' ' + describeBody(t));
          });
        }, function (e) { emit('offer_test', v[0] + ' -> blocked or failed: ' + scrub(e && e.name)); });
      }
      variants.reduce(function (p, v) { return p.then(function () { return one(v); }); }, Promise.resolve());
    }

    // ---- market experiment ----
    var realMarket = null;
    var REWRITE_HOSTS = /(xboxservices\.com|xboxlive\.com|gamepass\.com)$/i;
    var SKIP_HOSTS = /^(user|xsts|device|title)\.auth\.xboxlive\.com$|^login\./i;
    var MARKET_PARAMS = /^(market|mkt|country|countrycode|clientcountry)$/i;
    var LOCALE_PARAMS = /^(locale|clientlocale)$/i;

    function targetMarket() {
      try {
        var m = window.LabBridge && window.LabBridge.market && window.LabBridge.market();
        if (m && /^[A-Z]{2}$/.test(m)) return m;
      } catch (e) { }
      return 'ES';
    }

    function rewritableHost(urlStr) {
      try {
        var h = new URL(String(urlStr), location.href).hostname;
        return REWRITE_HOSTS.test(h) && !SKIP_HOSTS.test(h);
      } catch (e) { return false; }
    }

    function rewriteUrlString(s, M) {
      var out = { url: s, changed: false, note: '' };
      try {
        var a = new URL(String(s), location.href);
        if (!REWRITE_HOSTS.test(a.hostname) || SKIP_HOSTS.test(a.hostname)) return out;
        var pairs = [];
        a.searchParams.forEach(function (v, k) { pairs.push([k, v]); });
        pairs.forEach(function (kv) {                       // pass 1: learn the real market
          if (MARKET_PARAMS.test(kv[0]) && /^[A-Za-z]{2}$/.test(kv[1]) && !realMarket) realMarket = kv[1].toUpperCase();
        });
        var notes = [];
        pairs.forEach(function (kv) {                       // pass 2: rewrite
          var k = kv[0], v = kv[1];
          if (MARKET_PARAMS.test(k) && /^[A-Za-z]{2}$/.test(v)) {
            if (v.toUpperCase() !== M) { a.searchParams.set(k, M); notes.push(k + ':' + v.toUpperCase() + '>' + M); }
          } else if (LOCALE_PARAMS.test(k)) {
            var mm = /^([A-Za-z]{2,3})-([A-Za-z]{2})$/.exec(v);
            if (mm && realMarket && realMarket !== M && mm[2].toUpperCase() === realMarket) {
              var nv = mm[1].toLowerCase() + '-' + M;
              a.searchParams.set(k, nv); notes.push(k + ':' + v + '>' + nv);
            }
          }
        });
        if (notes.length) { out.url = a.toString(); out.changed = true; out.note = notes.join(','); }
      } catch (e) { }
      return out;
    }

    function rewriteHeaders(src, M) {
      try {
        var hh = new Headers(src || undefined);
        var cur = hh.get('x-xbl-market');
        if (cur === null) return null;
        if (!realMarket && /^[A-Za-z]{2}$/.test(cur)) realMarket = cur.toUpperCase();
        if (cur.toUpperCase() === M) return null;
        hh.set('x-xbl-market', M);
        return { headers: hh, note: 'x-xbl-market:' + cur.toUpperCase() + '>' + M };
      } catch (e) { return null; }
    }

    // returns null (nothing to change) or { promise } resolving to [input, init]
    function planRewrite(input, init) {
      var M = targetMarket();
      var isReq = (typeof Request === 'function') && (input instanceof Request);
      var urlStr = isReq ? input.url : String(input);
      if (!rewritableHost(urlStr)) return null;
      var u = rewriteUrlString(urlStr, M);
      var hdrSrc = (init && init.headers) ? init.headers : (isReq ? input.headers : null);
      var h = rewriteHeaders(hdrSrc, M);
      if (!u.changed && !h) return null;
      var note = [u.note, h && h.note].filter(Boolean).join(' ');
      var host = '';
      try { host = new URL(urlStr, location.href).hostname + maskPath(new URL(urlStr, location.href).pathname); } catch (e) { }
      emit('rewrite', host + ' ' + note + (isReq ? ' (Request object)' : ''));
      if (!isReq) {
        var ni = Object.assign({}, init || {});
        if (h) ni.headers = h.headers;
        return { promise: Promise.resolve([u.changed ? u.url : input, ni]) };
      }
      var method = String(input.method || 'GET').toUpperCase();
      var bodyP = (method === 'GET' || method === 'HEAD') ? Promise.resolve(undefined) : input.clone().arrayBuffer();
      return {
        promise: bodyP.then(function (buf) {
          var base = { method: input.method, headers: input.headers, body: buf, mode: input.mode, credentials: input.credentials,
                       cache: input.cache, redirect: input.redirect, referrer: input.referrer, referrerPolicy: input.referrerPolicy,
                       integrity: input.integrity, keepalive: input.keepalive, signal: input.signal };
          var merged = Object.assign(base, init || {});
          if (h) merged.headers = h.headers;
          return [new Request(u.changed ? u.url : input.url, merged), undefined];
        })
      };
    }

    var ofetch = window.fetch;
    var loggedFetch = null;
    if (ofetch) {
      loggedFetch = function (input, init) {
        var tag = 'GET ?';
        var rawUrl = '';
        try {
          var url = (typeof input === 'string') ? input : (input && input.url);
          var method = (init && init.method) || (input && input.method) || 'GET';
          tag = method + ' ' + safeUrl(url);
          emit('fetch', tag);
          var rd = reqDetail(url, init, (typeof input === 'string') ? null : input);
          if (rd) emit('fetch_request', tag + ' ' + rd);
          rawUrl = String(url);
        } catch (e) { }
        var p = ofetch.apply(this, arguments);
        try {
          p.then(function (r) { emit('fetch_status', tag + ' -> ' + r.status); captureShape(tag, rawUrl || '', r); captureOffering(tag, rawUrl || '', r, input, init); },
                 function (e) { emit('fetch_fail', tag + ' ' + scrub(e && e.name)); });
        } catch (e) { }
        return p;
      };
    }
    if (loggedFetch) {
      window.fetch = function (input, init) {
        var self = this;
        var plan = null;
        try { plan = planRewrite(input, init); } catch (e) { plan = null; }
        if (!plan) return loggedFetch.call(self, input, init);
        return plan.promise.then(
          function (args) { return loggedFetch.call(self, args[0], args[1]); },
          function (err) { emit('rewrite_failed', scrub(err && err.name)); return loggedFetch.call(self, input, init); }
        );
      };
    }

    var oopen = window.XMLHttpRequest && XMLHttpRequest.prototype.open;
    if (oopen) {
      XMLHttpRequest.prototype.open = function (m, u) {
        try { emit('xhr', m + ' ' + safeUrl(u)); } catch (e) { }
        return oopen.apply(this, arguments);
      };
    }

    if (window.RTCPeerConnection && RTCPeerConnection.prototype.setRemoteDescription) {
      var osrd = RTCPeerConnection.prototype.setRemoteDescription;
      RTCPeerConnection.prototype.setRemoteDescription = function (d) {
        try { emit('rtc_remote_description', d && d.type); } catch (e) { }
        return osrd.apply(this, arguments);
      };
    }

    function wrapCtor(name, describe) {
      try {
        var C = window[name];
        if (!C || typeof Proxy !== 'function') return;
        window[name] = new Proxy(C, {
          construct: function (target, args, newTarget) {
            try { emit(name, describe(args)); } catch (e) { }
            return Reflect.construct(target, args, newTarget);
          }
        });
      } catch (e) { }
    }
    wrapCtor('WebSocket', function (a) { return safeUrl(a[0]); });
    wrapCtor('Worker', function (a) { return safeUrl(a[0]); });
    wrapCtor('SharedWorker', function (a) { return safeUrl(a[0]); });
    wrapCtor('RTCPeerConnection', function () { return 'created'; });

    ['pushState', 'replaceState'].forEach(function (m) {
      try {
        var o = history[m];
        history[m] = function (s, t, u) {
          try { emit('history.' + m, u == null ? '' : safeUrl(u)); } catch (e) { }
          return o.apply(this, arguments);
        };
      } catch (e) { }
    });

    try {
      var odo = document.open;
      document.open = function () {
        try { emit('document.open', location.host + maskPath(location.pathname)); } catch (e) { }
        return odo.apply(this, arguments);
      };
    } catch (e) { }

    if (isTop && navigator.serviceWorker) {
      try {
        var oreg = navigator.serviceWorker.register;
        if (oreg) {
          navigator.serviceWorker.register = function (u) {
            try { emit('sw_register', safeUrl(u)); } catch (e) { }
            return oreg.apply(this, arguments);
          };
        }
        setTimeout(function () {
          try {
            navigator.serviceWorker.getRegistrations().then(function (rs) {
              emit('service_workers', rs.length + ' registered ' + rs.map(function (r) { return safeUrl(r.scope); }).join(','));
            }, function () { });
          } catch (e) { }
        }, 6000);
      } catch (e) { }
    }

    window.addEventListener('error', function (e) { emit('js_error', scrub(e && e.message)); }, true);
    window.addEventListener('unhandledrejection', function (e) {
      var r = e && e.reason;
      emit('rejection', scrub((r && (r.message || r.name)) || r));
    });

    function scan() {
      try {
        var t = ((document.body && document.body.innerText) || '').toLowerCase();
        var keys = ["not available in your region", "isn't available in your region", 'unsupported', 'not supported',
                    'browser', 'sign in', 'preview', 'game pass', 'install', 'something went wrong'];
        var hits = keys.filter(function (k) { return t.indexOf(k) >= 0; });
        emit('page_hints', JSON.stringify({ title: scrub(document.title).slice(0, 60), hits: hits, textLength: t.length }));
      } catch (e) { }
    }
    if (isTop) {
      setTimeout(scan, 8000);
      setTimeout(scan, 25000);
    }
  } catch (e) { }
})();
