/* Xbox Lab probe v10 (market + experiment-flag patch: defaultOffering CLOUDGAMING -> XGPUWEB, streaming-server header). Runs at document start on play.xbox.com / www.xbox.com.
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
        try {
          var hh2 = new Headers(h || undefined), ipn = ['forwarded', 'clientip', 'x-forwarded-for', 'x-client-ip'];
          ipn.forEach(function (nm) {
            var v = hh2.get(nm);
            if (v !== null) emit('ip_header', a.hostname + ' ' + nm + ' value-class=' + (/\b\d{1,3}(\.\d{1,3}){3}\b/.test(v) ? 'ipv4' : (/:[0-9a-f]*:/i.test(v) ? 'ipv6' : 'other')));
          });
        } catch (e) { }
        var key = a.hostname + maskPath(a.pathname);
        if (seenReq[key]) return null;
        seenReq[key] = 1;
        return 'params[' + names.join(',') + '] headers[' + hdrs.join(',') + ']';
      } catch (e) { return null; }
    }

    var OK_KEYS = /^(territory|ipderivedterritory|ipterritory|clientcountry|id|offering|offerings|offeringid|offeringids|hasaccess|access|allowed|isavailable|tier|subscription|type|name|kind|state|status|market|region|regions|country|countrycode|locale|culture|language|lang|code|availability|reason|message|action|actions|platform|platforms|cloud|isxcloud|xcloud|supported|enabled|available|iscloud|offeringsettings|allowregionselection|isdefaultregion)$/i;
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
    var SHAPE_URLS = /(emerald\.xboxservices\.com\/xboxcomfd\/experimentation|xCloudWebHome|\/api\/details\/[^\/]+\/actions|catalog\.gamepass\.com\/sigls\/v3|contentaccess\.exp\.xboxservices\.com\/all\/v1|title\.mgt\.xboxlive\.com\/titles\/default\/endpoints)/;
    var shapeCount = {};
    var OFFER_URL = /contentaccess\.exp\.xboxservices\.com\/all\/v1/;
    function captureOffering(tag, urlStr, r, input, init) {
      try {
        if (!OFFER_URL.test(urlStr)) return false;
        var hsrc = (init && init.headers) ? init.headers : ((typeof Request === 'function' && input instanceof Request) ? input.headers : null);
        var ct = r.headers && r.headers.get ? r.headers.get('content-type') : '';
        r.clone().arrayBuffer().then(function (buf) {
          var u8 = new Uint8Array(buf);
          emit('offer_baseline', r.status + ' ct=' + scrub(ct) + ' ' + describeBinary(u8, false));
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
        }, function () {
          r.clone().arrayBuffer().then(function (b) { emit('shape', tag.split(' ')[1].replace(/^https?:\/\//, '') + ' => ' + describeBinary(new Uint8Array(b), false)); }, function () { });
        });
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

    // ---- offering analysis (v5) ----
    var BYPASS_IPS = { US: '143.244.47.65', BR: '169.150.198.66', KR: '121.125.60.151', JP: '138.199.21.239',
                       PL: '45.134.212.66', ES: '80.58.61.250', GB: '62.24.134.1', FR: '212.27.40.240' };
    function fnv(u8) {
      var h = 0x811c9dc5;
      for (var i = 0; i < u8.length; i++) { h ^= u8[i]; h = Math.imul(h, 0x01000193); }
      return (h >>> 0).toString(16);
    }
    function findBytes(u8, str) {
      var n = str.length, codes = [];
      for (var k = 0; k < n; k++) codes.push(str.charCodeAt(k));
      for (var i = 0; i + n <= u8.length; i++) {
        var ok = true;
        for (var j = 0; j < n; j++) { if (u8[i + j] !== codes[j]) { ok = false; break; } }
        if (ok) return i;
      }
      return -1;
    }
    function upperTokens(u8) {
      var out = {}, cur = '';
      for (var i = 0; i <= u8.length; i++) {
        var c = i < u8.length ? u8[i] : 0;
        if ((c >= 65 && c <= 90) || (c >= 48 && c <= 57) || c === 95) cur += String.fromCharCode(c);
        else {
          if (cur.length >= 6 && cur.length <= 40 && /[A-Z]/.test(cur) && /^[A-Z]/.test(cur)) out[cur] = (out[cur] || 0) + 1;
          cur = '';
        }
      }
      return out;
    }
    function readVarint(u8, p) {
      var r = 0, mul = 1, b;
      do {
        if (p >= u8.length || mul > 4e15) return null;
        b = u8[p++]; r += (b & 0x7f) * mul; mul *= 128;
      } while (b & 0x80);
      return [r, p];
    }
    function parseMsg(u8, start, end) {
      var fields = [], p = start;
      while (p < end) {
        var t = readVarint(u8, p); if (!t) return null; p = t[1];
        var f = Math.floor(t[0] / 8), wt = t[0] % 8;
        if (f < 1 || f > 100000) return null;
        if (wt === 0) { var v = readVarint(u8, p); if (!v) return null; fields.push({ f: f, wt: 0, v: v[0] }); p = v[1]; }
        else if (wt === 1) { if (p + 8 > end) return null; fields.push({ f: f, wt: 1 }); p += 8; }
        else if (wt === 5) { if (p + 4 > end) return null; fields.push({ f: f, wt: 5 }); p += 4; }
        else if (wt === 2) {
          var l = readVarint(u8, p); if (!l) return null; p = l[1];
          if (p + l[0] > end) return null;
          fields.push({ f: f, wt: 2, s: p, e: p + l[0] }); p += l[0];
        } else return null;
      }
      return p === end ? fields : null;
    }
    function printableText(u8, s, e) {
      if (e - s === 0) return '';
      var n = 0;
      for (var i = s; i < e; i++) { var c = u8[i]; if (c >= 32 && c < 127) n++; }
      if (n / (e - s) < 0.95) return null;
      var t = '';
      for (var j = s; j < Math.min(e, s + 80); j++) t += String.fromCharCode(u8[j]);
      return t;
    }
    // render a length-delimited field: nested message, text, or bytes
    function renderField(u8, fd, depth) {
      var txt = printableText(u8, fd.s, fd.e);
      var nested = (depth < 7 && fd.e - fd.s > 1) ? parseMsg(u8, fd.s, fd.e) : null;
      if (nested && nested.length && (txt === null || fd.e - fd.s > 80 && nested.length > 1)) return renderMsg(u8, nested, depth + 1);
      if (txt !== null) return JSON.stringify(scrubValue(txt));
      return 'bytes[' + (fd.e - fd.s) + ']';
    }
    function renderMsg(u8, fields, depth) {
      var parts = [];
      for (var i = 0; i < fields.length && i < 24; i++) {
        var fd = fields[i];
        if (fd.wt === 0) parts.push(fd.f + ':' + fd.v);
        else if (fd.wt === 2) parts.push(fd.f + ':' + renderField(u8, fd, depth));
        else parts.push(fd.f + ':fixed');
      }
      if (fields.length > 24) parts.push('..+' + (fields.length - 24));
      return '{' + parts.join(' ') + '}';
    }
    // find the message that directly contains the needle string and render it, plus the path of field numbers leading to it
    function describeAround(u8, needle) {
      var idx = findBytes(u8, needle);
      if (idx < 0) return 'needle-not-found';
      var s = 0, e = u8.length, path = [], best = null;
      for (var depth = 0; depth < 10; depth++) {
        var fields = parseMsg(u8, s, e);
        if (!fields) break;
        var hit = null;
        for (var i = 0; i < fields.length; i++) { if (fields[i].wt === 2 && fields[i].s <= idx && idx < fields[i].e) { hit = fields[i]; break; } }
        if (!hit) break;
        path.push(hit.f);
        var child = parseMsg(u8, hit.s, hit.e);
        if (child && child.length > 1) { best = { s: hit.s, e: hit.e, fields: child }; s = hit.s; e = hit.e; }
        else break;
      }
      if (!best) return 'could-not-decode (needle at byte ' + idx + ')';
      return 'path=' + path.join('>') + ' ' + renderMsg(u8, best.fields, 0).slice(0, 1600);
    }
    function describeBinary(u8, withTree) {
      var toks = upperTokens(u8), names = Object.keys(toks).sort();
      var shown = names.slice(0, 50).map(function (t) { return maskPiece(t); }).join('|');
      var cloud = findBytes(u8, 'CLOUDGAMING') >= 0;
      var out = 'bin len=' + u8.length + ' fnv=' + fnv(u8) + ' hasCLOUDGAMING=' + cloud + ' upperTokens=' + names.length + (withTree ? ' [' + shown + ']' : '');
      if (withTree) {
        var rootF = parseMsg(u8, 0, u8.length);
        if (rootF) {
          var counts = {};
          rootF.forEach(function (f) { counts[f.f] = (counts[f.f] || 0) + 1; });
          out += ' rootFields=' + JSON.stringify(counts);
        } else out += ' rootNotProtobuf';
        if (cloud) out += ' AROUND_CLOUDGAMING: ' + describeAround(u8, 'CLOUDGAMING');
      }
      return out;
    }
    function diffSummary(a, b) {
      if (a.length !== b.length) return 'lengthDiffers(' + a.length + ' vs ' + b.length + ')';
      var n = 0, first = -1, last = -1;
      for (var i = 0; i < a.length; i++) { if (a[i] !== b[i]) { n++; if (first < 0) first = i; last = i; } }
      return n + ' bytes differ' + (n ? ' (first ' + first + ', last ' + last + ')' : '');
    }
    function describeBody(t) {   // text bodies (kept for the JSON endpoints)
      try { return 'json ' + shape(JSON.parse(t), 0, '').slice(0, 1500); } catch (e) { }
      return 'non-json text len=' + String(t).length;
    }
    var offerTestsDone = false;
    function offeringTests(urlStr, headersSrc, baseU8) {
      if (offerTestsDone) return;
      offerTestsDone = true;
      var M = '';
      try { M = (window.LabBridge && window.LabBridge.market && window.LabBridge.market()) || ''; } catch (e) { }
      var ip = BYPASS_IPS[M] || BYPASS_IPS.US;
      var real = realMarket || 'GR';
      var tests = [
        ['repeat of the page request', null, null],
        ['market=' + real + ' (your real one)', real, null],
        ['market=ES', 'ES', null], ['market=GB', 'GB', null], ['market=PL', 'PL', null],
        ['x-forwarded-for=' + ip, M || 'US', ['x-forwarded-for', ip]],
        ['forwarded=for=' + ip, M || 'US', ['forwarded', 'for=' + ip]],
        ['clientip=' + ip, M || 'US', ['clientip', ip]]
      ];
      function one(t) {
        var a = new URL(urlStr);
        if (t[1]) a.searchParams.set('market', t[1]);
        var h = new Headers(headersSrc || undefined);
        if (t[2]) h.set(t[2][0], t[2][1]);
        return ofetch.call(window, a.toString(), { method: 'GET', headers: h, mode: 'cors' }).then(function (r) {
          return r.arrayBuffer().then(function (buf) {
            var u8 = new Uint8Array(buf);
            emit('offer_test', t[0] + ' -> ' + r.status + ' ' + describeBinary(u8, false) + ' diffVsPage: ' + diffSummary(baseU8, u8));
          });
        }, function (e) { emit('offer_test', t[0] + ' -> blocked or failed: ' + scrub(e && e.name)); });
      }
      tests.reduce(function (p, t) { return p.then(function () { return one(t); }); }, Promise.resolve());
    }

    // ---- site-code reader + client-state inventory (v6) ----
    var bundlesScanned = false;
    function scanBundles() {
      try {
        if (!isTop || bundlesScanned) return;
        bundlesScanned = true;
        var urls = [], seenU = {};
        var add = function (u) {
          try {
            var a = new URL(u, location.href);
            if (a.origin === location.origin && /\.m?js$/.test(a.pathname) && !seenU[a.pathname]) { seenU[a.pathname] = 1; urls.push(a.href); }
          } catch (e) { }
        };
        Array.prototype.forEach.call(document.querySelectorAll('script[src]'), function (el) { add(el.src); });
        Array.prototype.forEach.call(document.querySelectorAll('link[rel=modulepreload],link[rel=preload]'), function (el) { add(el.href); });
        try { performance.getEntriesByType('resource').forEach(function (r) { add(r.name); }); } catch (e) { }
        emit('bundles', urls.length + ' scripts: ' + urls.slice(0, 40).map(function (u) { return new URL(u).pathname; }).join(' '));
        var NEEDLES = [[/[,;{(\s]yl=[^,;]{0,160}/, 3, 260], ['Invalid market-decision territory specified via developer c', 1, 700], [/ipDerivedTerritory:\s*this\.createRelationalQuery/, 1, 900], ['Unknown offering with ID', 1, 900], ['native bridge absent', 1, 900]];
        var found = {}, total = 0;
        urls.slice(0, 80).reduce(function (p, u) {
          return p.then(function () {
            return ofetch.call(window, u, { cache: 'force-cache' }).then(function (r) { return r.text(); }).then(function (t) {
              NEEDLES.forEach(function (nd) {
                var need = nd[0], from = 0, idx, mlen, label = String(need);
                for (;;) {
                  if ((found[label] || 0) >= nd[1]) break;
                  if (need instanceof RegExp) { var rm = need.exec(t.slice(from)); if (!rm) break; idx = from + rm.index; mlen = rm[0].length; }
                  else { idx = t.indexOf(need, from); if (idx < 0) break; mlen = need.length; }
                  found[label] = (found[label] || 0) + 1;
                  from = idx + mlen;
                  var ctx = t.slice(Math.max(0, idx - nd[2]), Math.min(t.length, idx + mlen + nd[2])).replace(/\s+/g, ' ');
                  total += ctx.length;
                  if (total < 50000) emit('code_hit', label.slice(0, 60) + ' in ' + new URL(u).pathname + ' @' + idx + ': ' + ctx);
                }
              });
            }, function () { });
          });
        }, Promise.resolve());
      } catch (e) { }
    }
    function inventory() {
      try { emit('cookie_names', document.cookie.split(';').map(function (c) { return maskPiece(c.split('=')[0].trim()); }).filter(Boolean).slice(0, 40).join(',')); } catch (e) { }
      try {
        var ls = [], ss = [], i;
        for (i = 0; i < localStorage.length; i++) ls.push(localStorage.key(i));
        for (i = 0; i < sessionStorage.length; i++) ss.push(sessionStorage.key(i));
        emit('storage_keys', 'local[' + ls.slice(0, 60).map(maskPiece).join(',') + '] session[' + ss.slice(0, 40).map(maskPiece).join(',') + ']');
      } catch (e) { emit('storage_keys', 'unavailable'); }
      try { if (window.caches && caches.keys) caches.keys().then(function (ks) { emit('cache_names', ks.slice(0, 20).map(maskPiece).join(',')); }, function () { }); } catch (e) { }
      try { if (window.indexedDB && indexedDB.databases) indexedDB.databases().then(function (dbs) { emit('indexeddb', dbs.slice(0, 20).map(function (d) { return maskPiece(d.name); }).join(',')); }, function () { }); } catch (e) { }
      try { emit('window_keys', Object.keys(window).filter(function (k) { return /^__|state|config|remix|store|offer|router|apollo|redux/i.test(k); }).slice(0, 40).join(',')); } catch (e) { }
    }
    var lastRes = 0;
    function dumpResources(why) {
      try {
        var es = performance.getEntriesByType('resource').slice(lastRes);
        lastRes += es.length;
        var seenR = {}, out = [];
        es.forEach(function (e) {
          if (/^(img|css|link|script|audio|video)$/.test(e.initiatorType)) return;
          var u = safeUrl(e.name) + ' [' + e.initiatorType + ']';
          if (!seenR[u]) { seenR[u] = 1; out.push(u); }
        });
        emit('resources_' + why, out.slice(0, 50).join(' ;; '));
      } catch (e) { }
    }

    // ---- the site's own log + cached state (v7) ----
    var PAGELOG_RE = /offering|stream|gate|launch|territory|eligib|title-?info|region|market|cloud|gssv|xgpu|enrol|unsupported|not available|failed|error|denied|forbidden|flight|experiment|browserSupport|sentry|exception/i;
    var PAGELOG_NOISE = /RelationalQueryObserver|ServiceWorkerManager|Initialized system|userSamplingRate|refresh-trial-time|setSeenESRB|doTrackedFetch/i;
    function scrubLog(t) {
      return String(t)
        .replace(/Bearer\s+[A-Za-z0-9._~+\/=-]+/g, 'Bearer {token}')
        .replace(/XBL3\.0 x=[^"'\s]+/g, 'XBL3.0 {token}')
        .replace(/("?(access_token|refresh_token|id_token|token|gsToken|authorization)"?\s*[:=]\s*)"?[^"&,\s}]+/gi, '$1{token}')
        .replace(/(gamertag|displayName|userName|firstName|lastName|realName|modernGamertag|uniqueModernGamertag)\\?"?\s*[:=]\s*\\?"?[^"\\,;}]*/gi, '$1:{name}')
        .replace(/https?:\/\/[^\s"',)]+/g, function (u) { try { return new URL(u).host; } catch (e) { return '{url}'; } })
        .replace(/[^\s@"']+@[^\s@"']+/g, '{email}')
        .replace(/eyJ[A-Za-z0-9_-]{10,}(\.[A-Za-z0-9_-]+){0,2}/g, '{jwt}')
        .replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/ig, '{guid}')
        .replace(/[0-9a-f]{16,}/ig, '{hex}')
        .replace(/[0-9]{6,}/g, '{num}')
        .replace(/\s+/g, ' ');
    }
    function readDb(name, mode, why) {
      try {
        var req = indexedDB.open(name);
        req.onerror = function () { emit('pagedb_error', why + ' ' + maskPiece(name)); };
        req.onsuccess = function () {
          var db = req.result;
          try {
            var stores = Array.prototype.slice.call(db.objectStoreNames);
            emit('pagedb_stores', why + ' ' + maskPiece(name) + ' stores=' + stores.join(','));
            stores.slice(0, 4).forEach(function (sn) {
              var st = db.transaction(sn, 'readonly').objectStore(sn);
              var kept = [], seen = 0, shaped = false, seenNorm = {};
              var cur = st.openCursor(null, mode === 'recent' ? 'prev' : 'next');
              cur.onsuccess = function () {
                var c = cur.result;
                if (!c || seen >= (mode === 'recent' ? 700 : 900)) {
                  var ordered = (mode === 'recent' ? kept.reverse() : kept);
                  if (mode === 'recent') {
                    var chunk = '', part = 0;
                    ordered.forEach(function (ln, ix) {
                      if (chunk.length + ln.length > 5200) { emit('pagedb_recent', why + ' ' + maskPiece(name) + ' part' + (++part) + ' :: ' + chunk); chunk = ''; }
                      chunk += (chunk ? ' ;; ' : '') + ln;
                    });
                    emit('pagedb_recent', why + ' ' + maskPiece(name) + ' part' + (++part) + ' scanned=' + seen + ' kept=' + ordered.length + ' :: ' + chunk);
                  } else {
                    emit('pagedb_' + mode, why + ' ' + maskPiece(name) + '/' + sn + ' scanned=' + seen + ' kept=' + ordered.length + ' :: ' + ordered.join(' ;; ').slice(0, 3000));
                  }
                  try { db.close(); } catch (e) { }
                  return;
                }
                seen++;
                var rec = c.value, text = '';
                try { text = (typeof rec === 'string') ? rec : JSON.stringify(rec); } catch (e) { }
                if (!shaped) { shaped = true; try { emit('pagedb_shape', maskPiece(name) + '/' + sn + ' key=' + maskPiece(String(c.key)) + ' ' + shape(rec, 0, '').slice(0, 500)); } catch (e) { } }
                if (text && kept.length < 70) {
                  if (mode === 'recent') {
                    var lg = (rec && rec.data && typeof rec.data.log === 'string') ? rec.data.log : text;
                    if (PAGELOG_RE.test(lg) && !PAGELOG_NOISE.test(lg)) {
                      var norm = lg.replace(/^\S+\s/, '').replace(/[0-9]+/g, '#').slice(0, 170);
                      if (!seenNorm[norm]) { seenNorm[norm] = 1; kept.push(scrubLog(lg).slice(0, 900)); }
                    }
                  } else {
                    var m = /offering/i.exec(text);
                    if (m) kept.push(maskPiece(String(c.key)) + ': ' + scrubLog(text.slice(Math.max(0, m.index - 220), m.index + 260)));
                  }
                }
                c.continue();
              };
              cur.onerror = function () { try { db.close(); } catch (e) { } };
            });
          } catch (e) { try { db.close(); } catch (e2) { } }
        };
      } catch (e) { }
    }
    function readPageStores(why) {
      try {
        if (!window.indexedDB || !indexedDB.databases) return;
        indexedDB.databases().then(function (dbs) {
          dbs.forEach(function (d) {
            var n = d.name || '';
            if (/^PlayXboxAppLogs/.test(n)) readDb(n, 'recent', why);
          });
        }, function () { });
      } catch (e) { }
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

    var IP_HEADERS = ['forwarded', 'clientip', 'x-forwarded-for', 'x-client-ip'];
    function swapIp(name, value, ip) {
      var v = String(value);
      var v4 = /\b\d{1,3}(\.\d{1,3}){3}\b/;
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
          var v = hh.get(nm);
          if (v === null) return;
          var nv = swapIp(nm, v, ip);
          if (nv !== null && nv !== v) { hh.set(nm, nv); notes.push(nm + ':client-ip>' + M + '-ip'); changed = true; }
        });
        var gssv = !!host && /\.gssv-play-prod\.xboxlive\.com$/i.test(host);
        if (gssv && hh.get('x-forwarded-for') === null) { hh.set('x-forwarded-for', ip); notes.push('gssv:x-forwarded-for added'); changed = true; }
        return changed ? { headers: hh, note: notes.join(','), gssv: gssv } : null;
      } catch (e) { return null; }
    }

    function rewriteBodyMarket(body, M) {
      // JSON bodies sent as strings: make market/country fields match the target market. Returns {body, note} or null.
      try {
        if (typeof body !== 'string' || body.charAt(0) !== '{' && body.charAt(0) !== '[') return null;
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
    function bodyShape(body) {
      try { if (typeof body === 'string' && (body.charAt(0) === '{' || body.charAt(0) === '[')) return shape(JSON.parse(body), 0, '').slice(0, 500); } catch (e) { }
      return null;
    }

    var EXP_URL = /emerald\.xboxservices\.com\/xboxcomfd\/experimentation/;
    function patchExperimentation(r) {
      try {
        if (!r || !r.ok) return r;
        return r.clone().json().then(function (j) {
          try {
            var tr0 = j && j.exp && j.exp.treatments && j.exp.treatments.PlayXbox;
            if (tr0) {
              var out0 = [];
              Object.keys(tr0).forEach(function (k) {
                if (/offering|cloud|stream|xgpu|region|territory|market|gate/i.test(k)) out0.push(k + '=' + scrubLog(JSON.stringify(tr0[k])).slice(0, 220));
              });
              emit('exp_treatments_original', out0.join(' ;; ').slice(0, 4000));
            }
          } catch (e) { }
          var changes = [];
          (function walk(o, path, d) {
            if (!o || typeof o !== 'object' || d > 9) return;
            Object.keys(o).forEach(function (k) {
              var v = o[k];
              if (typeof v === 'string' && v.length < 4000 && /cloudgaming/i.test(v)) {
                o[k] = v.replace(/CLOUDGAMING/g, 'XGPUWEB').replace(/cloudgaming/g, 'xgpuweb').replace(/CloudGaming/g, 'XgpuWeb');
                changes.push(maskKey(path + '.' + k));
              } else if (v && typeof v === 'object') walk(v, path + '.' + k, d + 1);
            });
          })(j, '', 0);
          try {
            var tr = j && j.exp && j.exp.treatments && j.exp.treatments.PlayXbox;
            if (tr) {
              var out = [];
              Object.keys(tr).forEach(function (k) {
                if (/offering|cloud|stream|xgpu|region|territory|market|gate/i.test(k)) out.push(k + '=' + scrubLog(JSON.stringify(tr[k])).slice(0, 220));
              });
              emit('exp_treatments_after_patch', out.join(' ;; ').slice(0, 4000));
            }
            var fl = j && j.exp && j.exp.flights;
            if (fl && fl.filter) emit('exp_flights', fl.filter(function (x) { return /offering|cloud|stream|xgpu|region|territory|market|gate/i.test(String(x)); }).slice(0, 40).join(','));
          } catch (e) { }
          emit('exp_patch', changes.length ? 'changed ' + changes.length + ' value(s): ' + changes.slice(0, 8).join(',') : 'no CLOUDGAMING value found in the answer');
          if (!changes.length) return r;
          var hdrs = new Headers(r.headers); hdrs.delete('content-length'); hdrs.delete('content-encoding');
          var nr = new Response(JSON.stringify(j), { status: r.status, statusText: r.statusText, headers: hdrs });
          try { Object.defineProperty(nr, 'url', { value: r.url }); } catch (e) { }
          return nr;
        }, function () { return r; });
      } catch (e) { return r; }
    }

    // returns null (nothing to change) or { promise } resolving to [input, init]
    function planRewrite(input, init) {
      var M = targetMarket();
      var isReq = (typeof Request === 'function') && (input instanceof Request);
      var urlStr = isReq ? input.url : String(input);
      if (!rewritableHost(urlStr)) return null;
      var u = rewriteUrlString(urlStr, M);
      var hdrSrc = (init && init.headers) ? init.headers : (isReq ? input.headers : null);
      var hostName = '';
      try { hostName = new URL(urlStr, location.href).hostname; } catch (e) { }
      var h = rewriteHeaders(hdrSrc, M, hostName);
      var bm0 = (!isReq && init && typeof init.body === 'string') ? rewriteBodyMarket(init.body, M) : null;
      if (!u.changed && !h && !bm0) return null;
      var bm = (!isReq && init && typeof init.body === 'string') ? rewriteBodyMarket(init.body, M) : null;
      if (bm) { h = h || {}; }
      var note = [u.note, h && h.note, bm && bm.note].filter(Boolean).join(' ');
      var host = '';
      try { host = new URL(urlStr, location.href).hostname + maskPath(new URL(urlStr, location.href).pathname); } catch (e) { }
      emit('rewrite', host + ' ' + note + (isReq ? ' (Request object)' : ''));
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
          if (init && init.body && /catalog\.gamepass\.com/.test(String(url))) { var bsh = bodyShape(init.body); if (bsh) emit('post_body_shape', tag + ' ' + bsh); }
          rawUrl = String(url);
        } catch (e) { }
        var p = ofetch.apply(this, arguments);
        try {
          p.then(function (r) { emit('fetch_status', tag + ' -> ' + r.status); captureShape(tag, rawUrl || '', r); captureOffering(tag, rawUrl || '', r, input, init); },
                 function (e) { emit('fetch_fail', tag + ' ' + scrub(e && e.name)); });
        } catch (e) { }
        if (EXP_URL.test(rawUrl || '')) return p.then(patchExperimentation);
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
          function (args) {
            var q = loggedFetch.call(self, args[0], args[1]);
            if (plan.gssvAdded) return q.catch(function (e) { emit('gssv_header_blocked', scrub(e && e.name)); return loggedFetch.call(self, input, init); });
            return q;
          },
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
          try { if (/\/stream\//.test(String(u))) { setTimeout(function () { dumpResources('after_stream_route'); readPageStores('after_stream_route'); }, 4500); setTimeout(function () { readPageStores('later'); }, 15000); } } catch (e) { }
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
    if (isTop && location.host === 'play.xbox.com') {
      setTimeout(inventory, 7000);
      setTimeout(function () { readPageStores('startup'); }, 20000);
      setTimeout(scanBundles, 25000);
    }
  } catch (e) { }
})();
