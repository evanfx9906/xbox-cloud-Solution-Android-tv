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

    // ---- callbacks the ported handover expects on window (native app -> page), unchanged ----
// Bridge for Native Android WebRTC
window.handleAnswer = function(sdp) {
    console.log("[BxC] handleAnswer from Java, sdp length: " + (sdp ? sdp.length : 0));
    if (window.pendingAnswerResolver) {
        window.pendingAnswerResolver({ type: 'answer', sdp: sdp });
        window.pendingAnswerResolver = null;
    } else {
        console.warn("[BxC] No pendingAnswerResolver found");
    }
};

window.handleOffer = function(sdp) {
    console.log("[BxC] handleOffer from Java, sdp length: " + (sdp ? sdp.length : 0));
    if (window.pendingOfferResolver) {
        window.pendingOfferResolver({ type: 'offer', sdp: sdp });
        window.pendingOfferResolver = null;
    } else {
        console.warn("[BxC] No pendingOfferResolver found");
    }
};

window.handleIceCandidate = function(sdpMid, sdpMLineIndex, sdp) {
    console.log("[BxC] handleIceCandidate from Java: " + sdpMid + " sdp length: " + (sdp ? sdp.length : 0));
    if (window.peer && window.peer.onicecandidate) {
        window.peer.onicecandidate({
            candidate: {
                candidate: sdp,
                sdpMid: sdpMid,
                sdpMLineIndex: sdpMLineIndex
            }
        });
    } else {
        console.warn("[BxC] handleIceCandidate: peer or onicecandidate missing");
    }
};

window.handleDataChannelMessage = function(label, binaryData, textData, isBinary) {
    console.log("[BxC] handleDataChannelMessage: " + label + " (binary: " + isBinary + ")");
    const dc = window.proxyDataChannels && window.proxyDataChannels[label];
    if (dc) {
        let data;
        if (isBinary) {
            data = window.bxToArrayBuffer(binaryData);
        } else {
            data = textData;
        }

        console.warn("[BxC] recivin data from channel " + label + ", data: " + data);
        if(label=='message'&&data.includes('HandshakeAck')){
        async function CXkeepalive(){

                                                            let CXtoken =  window.BX_EXPOSED.streamSession.gsToken;
                                                            let CXsessionPath=window.BX_EXPOSED.streamSession.sessionPath;
                                                            let CXendPoint=window.BX_EXPOSED.streamSession.domainName;
                                                            if(CXtoken.length&&CXtoken.length>0&&CXsessionPath.length&&CXsessionPath.length>0&&CXendPoint.length&&CXendPoint.length>0)
                                                           {
                                                            let CXurl=CXendPoint+'/'+CXsessionPath+'/keepalive';
                                                            console.log("[BxC] Keepalive URL:", CXurl,' token: ',CXtoken);
                                                             if (window.AndroidBridge && window.AndroidBridge.keepalive) {
                                                                            window.AndroidBridge.keepalive(CXurl,CXtoken);
                                                                        }
                                                                        return;}
                                                                        return setTimeout(CXkeepalive,10);
                                                           }
                                                       setTimeout(CXkeepalive,10);
        }
        // Create a real MessageEvent so the app can access .data
        const event = new MessageEvent('message', {
            data: data,
            origin: window.location.origin
        });
        dc.dispatchEvent(event);
        if (dc.onmessage) dc.onmessage(event);
    }
};

window.handleDataChannelState = function(label, state) {
    console.log("[BxC] handleDataChannelState: " + label + " -> " + state);
    const dc = window.proxyDataChannels && window.proxyDataChannels[label];
    if (dc) {
        dc.readyState = state.toLowerCase();
        if (dc.onopen && dc.readyState === 'open') dc.onopen();
        if (dc.onclose && dc.readyState === 'closed') dc.onclose();
    }
};

window.handleIceConnectionState = function(state) {
    console.log("[BxC] handleIceConnectionState: " + state);
    if (window.peer) {
        window.peer.iceConnectionState = state.toLowerCase();
        if (window.peer.oniceconnectionstatechange) window.peer.oniceconnectionstatechange();
        if (window.peer._listeners['iceconnectionstatechange']) {
            window.peer._listeners['iceconnectionstatechange'].forEach(l => l());
        }
    }
};

window.setControllerSettings = function(deadzone, sensitivity) {
    setPref("controller.deadzone", deadzone);
    setPref("controller.sensitivity", sensitivity);
}

window.setUseUnreliableInput = function(enabled) {
    window.BX_USE_UNRELIABLE_INPUT = enabled;
    BxLogger.info("Settings", "Updated UseUnreliableInput to:", enabled);
}
window.setPref = function lsSet(key, value) {
    localStorage.setItem(key, value);
};

window.getPref=function lsget(key){
return localStorage.getItem(key);
}


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


    // ---- EXPERIMENT (v12): the native WebRTC handover, ported from the proven working build -------
    // Hands the stream to the native decoder instead of the browser's own WebRTC, and sends the same
    // resolution/bitrate/region spoofing the working app always sent. UNTESTED on the new site: if
    // video never appears within ~15s after pressing Play, this is the part to revert.
    var BxLogger = { info: function () {}, error: function () {} };  // same shape, quiet (was console logging)
    if (!window.BX_EXPOSED) window.BX_EXPOSED = {};
    window.BX_EXPOSED.streamSession = window.BX_EXPOSED.streamSession || { gsToken: '', sessionPath: '', domainName: '' };
const BypassServerIps = {
    us: "143.244.47.65",
    br: "169.150.198.66",
    kr: "121.125.60.151",
    jp: "138.199.21.239",
    pl: "45.134.212.66",
    es: "80.58.61.250",
    uk: "62.24.134.1",
    fr: "212.27.40.240"
};

const ServerRegionMap = {
    us: "westus",
    br: "brazilsouth",
    kr: "koreacentral",
    jp: "japaneast",
    pl: "swedencentral",
    es: "spaincentral",
    uk: "uksouth",
    fr: "francecentral"
};

function getTargetRegion() {
    // Priority: window global > localStorage > default (us)
    return window.BX_TARGET_REGION || localStorage.getItem('BX_TARGET_REGION') || 'es';
}

function getTargetResolution() {
    // Priority: window global > localStorage > default (1080p)
    return window.BX_TARGET_RES || localStorage.getItem('BX_TARGET_RES') || '1080p';
}

function getTargetBitrate() {
    // Priority: window global > localStorage > default (0 - Auto)
    return window.BX_TARGET_BITRATE || parseInt(localStorage.getItem('BX_TARGET_BITRATE')) || 0;
}

function getOsNameFromResolution(resolution) {
    let osName;
    switch (resolution) {
        case "1080HQ":
            osName = "tizen";
            break;
        case "1080":
            osName = "windows";
            break;
        case "720":
            osName = "android";
            break;
        default:
            osName = "tizen";
            break;
    }
    return osName;
}

function generateMsDeviceInfo(osName) {
    return {
        appInfo: {
            env: {
                clientAppId: window.location.host,
                clientAppType: "browser",
                clientAppVersion: "26.1.97",
                clientSdkVersion: "10.3.7",
                httpEnvironment: "prod",
                sdkInstallId: ""
            }
        },
        dev: {
            os: { name: osName, ver: "22631.2715", platform: "desktop" },
            hw: { make: "Microsoft", model: "unknown", sdktype: "web" },
            browser: { browserName: "chrome", browserVersion: "140.0.3485.54" },
            displayInfo: {
                dimensions: { widthInPixels: 4096, heightInPixels: 2160 },
                pixelDensity: { dpiX: 1, dpiY: 1 }
            }
        }
    };
}
class XcloudInterceptor {
    static async handleLogin(request, init) {
        const region = getTargetRegion();
        const ip = BypassServerIps[region] || BypassServerIps.us;

        BxLogger.info("XcloudInterceptor", "Using bypass IP for login:", region, "->", ip);

        request.headers.set("X-Forwarded-For", ip);

        let response;
        try {
            response = await NATIVE_FETCH(request, init);
        } catch (e) {
            BxLogger.error("XcloudInterceptor", "Login interception failed", e);
            throw e;
        }

        if (response.status === 200) {
            const obj = await response.clone().json();

            const targetServerRegion = ServerRegionMap[region];

            if (targetServerRegion && obj.offeringSettings && obj.offeringSettings.regions) {
                BxLogger.info("XcloudInterceptor", "Forcing streaming region to:", targetServerRegion);

                const filteredRegions = obj.offeringSettings.regions.filter(r => r.name.toLowerCase().includes(targetServerRegion));
                if (filteredRegions.length > 0) {
                    filteredRegions[0].isDefault = true;
                    obj.offeringSettings.regions = filteredRegions;
                }
            }

            response.json = () => Promise.resolve(obj);
        }

        return response;
    }

    static async handlePlay(request, init) {
        const res = getTargetResolution();
        const osName = getOsNameFromResolution(res);
        const deviceInfo = generateMsDeviceInfo(osName);

        BxLogger.info("XcloudInterceptor", "Patching play request for resolution:", res, "-> OS:", osName);

        // Inject hardware spoofing header
        request.headers.set("x-ms-device-info", JSON.stringify(deviceInfo));

        let finalRequest = request;
        // Modify body to include spoofed OS name
        try {
            const body = await request.clone().json();
            if (body.settings) {
                body.settings.osName = osName;
                // Surgical addition: force English, mirroring Better xCloud's
                // "preferred game language" override (body.settings.locale) on this
                // exact same session-creation request.
                body.settings.locale = "en-US";
            }
            // Create a new request with the modified body
            finalRequest = new Request(request, {
                body: JSON.stringify(body)
            });
        } catch (e) {
            BxLogger.error("XcloudInterceptor", "Play request body modification failed", e);
        }

        const response = await NATIVE_FETCH(finalRequest, init);

        // Capture session info
        try {
            if (response.status >= 200 && response.status < 300) {
                const respBody = await response.clone().json();
                if (respBody.sessionPath) {
                    window.BX_EXPOSED.streamSession.sessionPath = respBody.sessionPath;
                    try { emit("native_session_captured", "yes"); } catch (e) { }
                }
                const url = typeof request === "string" ? request : request.url;
                // Use URL origin to avoid carrying over query parameters or path segments
                window.BX_EXPOSED.streamSession.domainName = new URL(url).origin;
                BxLogger.info("streamSession", "Captured sessionPath and domainName:", window.BX_EXPOSED.streamSession);
            }
        } catch (e) {
            BxLogger.error("XcloudInterceptor", "Session info capture failed", e);
        }

        return response;
    }

    static async handleConfiguration(request, init) {
        // Extract token from Authorization header
        const authHeader = request.headers.get("Authorization");
        if (authHeader && authHeader.startsWith("Bearer ")) {
            window.BX_EXPOSED.streamSession.gsToken = authHeader.substring(7);
            try { emit("native_token_captured", "yes"); } catch (e) { }
            BxLogger.info("streamSession", "Captured gsToken from configuration request headers");
        }

        let response = await NATIVE_FETCH(request, init);
        let text = await response.clone().text();
        if (!text.length) return response;

        try {
            let obj = JSON.parse(text);
            let overrides = JSON.parse(obj.clientStreamingConfigOverrides || "{}") || {};

            overrides.inputConfiguration = overrides.inputConfiguration || {};
            // Force unreliable input channel (unreliableinput) if enabled
            const useUnreliable = window.BX_USE_UNRELIABLE_INPUT !== false;
            overrides.inputConfiguration.useUnreliableInput = useUnreliable;
            overrides.inputConfiguration.enableVibration = true;

            obj.clientStreamingConfigOverrides = JSON.stringify(overrides);

            BxLogger.info("XcloudInterceptor", "Forcing input configuration - unreliableinput:", useUnreliable);

            // Reconstruct response
            const modifiedResponse = new Response(JSON.stringify(obj), {
                status: response.status,
                statusText: response.statusText,
                headers: response.headers
            });

            return modifiedResponse;
        } catch (e) {
            BxLogger.error("XcloudInterceptor", "Configuration modification failed", e);
        }

        return response;
    }

    static async handle(request, init) {
        const url = typeof request === "string" ? request : request.url;
        if (url.endsWith("/v2/login/user")) {
            return XcloudInterceptor.handleLogin(request, init);
        } else if (url.endsWith("/sessions/cloud/play")) {
            return XcloudInterceptor.handlePlay(request, init);
        } else if (url.endsWith("/configuration")) {
            return XcloudInterceptor.handleConfiguration(request, init);
        }
        return NATIVE_FETCH(request, init);
    }
}
function patchSdpBitrate(sdp, videoBitrate) {
    if (!videoBitrate) return sdp;

    let lines = sdp.split('\r\n');
    let newLines = [];
    let inVideoSection = false;

    for (let line of lines) {
        newLines.push(line);
        if (line.startsWith('m=video')) {
            inVideoSection = true;
        } else if (line.startsWith('m=')) {
            inVideoSection = false;
        }

        if (inVideoSection && line.startsWith('c=IN')) {
            // Inject b=AS line after connection info in video section
            newLines.push('b=AS:' + videoBitrate);
        }
    }
    return newLines.join('\r\n');
}

function patchSdpFps(sdp, fps) {
    let lines = sdp.split('\r\n');
    for (let i = 0; i < lines.length; i++) {
        if (lines[i].startsWith('a=fmtp:')) {
            if (!lines[i].includes('max-fr=')) {
                lines[i] += ';max-fr=' + fps;
            } else {
                lines[i] = lines[i].replace(/max-fr=\d+/, 'max-fr=' + fps);
            }
        }
    }
    return lines.join('\r\n');
}

function patchRtcPeerConnection() {
    let OrgRTCPeerConnection = window.RTCPeerConnection;
window.handleIceCandidate = function(sdpMid, sdpMLineIndex, candidateStr) {
    if (!window.peer) return;

    // If candidateStr is null/empty, WebRTC treats it as the end of candidates
    let candidateObj = candidateStr ? { sdpMid: sdpMid, sdpMLineIndex: sdpMLineIndex, candidate: candidateStr } : null;

    let event = new Event('icecandidate');
    event.candidate = candidateObj;

    if (window.peer.onicecandidate) window.peer.onicecandidate(event);
    if (window.peer._listeners && window.peer._listeners['icecandidate']) {
        window.peer._listeners['icecandidate'].forEach(l => l(event));
    }
};
    // Base64 Helpers
    window.bxToBase64 = function(buffer) {
        let binary = '';
        let bytes = new Uint8Array(buffer);
        for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
        return window.btoa(binary);
    };
    window.bxToArrayBuffer = function(base64) {
        let binary = window.atob(base64);
        let bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        return bytes.buffer;
    };


    window.simulateOnTrack = function(kind, id) {
        console.log("[BxC] Simulating ontrack for " + kind);

        let stream;
        let track;

        if (kind === 'video') {
            const canvas = document.createElement('canvas');
            canvas.width = 1920;
            canvas.height = 1080;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = 'black';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            ctx.fillStyle = 'white';
            ctx.font = '30px Arial';
            ctx.fillText('Native Bridge Active', 50, 50);

            stream = canvas.captureStream(60);
            track = stream.getVideoTracks()[0];
        } else {

                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const destination = audioCtx.createMediaStreamDestination();
                stream = destination.stream;
                track = stream.getAudioTracks()[0];
            }

        // Construct a real-like Track event
        let event = new Event('track');
        event.track = track;
        event.streams = [stream];
        event.transceiver = { receiver: { track: track } };

        if (window.peer) {
            if (window.peer.ontrack) window.peer.ontrack(event);
            if (window.peer._listeners && window.peer._listeners['track']) {
                window.peer._listeners['track'].forEach(l => l(event));
            }
        }
    };

    window.filterSdp = function(sdp) {
        let lines = sdp.split('\r\n');
        let newLines = [];
        let skipExtmap = [
            'urn:ietf:params:rtp-hdrext:toffset',
                        'urn:ietf:params:rtp-hdrext:sdes:rtp-stream-id',
                        'urn:ietf:params:rtp-hdrext:sdes:repaired-rtp-stream-id',
                        'http://www.webrtc.org/experiments/rtp-hdrext/video-layers-allocation00',
            'http://www.ietf.org/id/draft-holmer-rmcat-transport-wide-cc-extensions-01'
        ];

        for (let line of lines) {
            let skip = false;
            if (line.startsWith('a=extmap:')) {
                 for (let ext of skipExtmap) {
                                      if (line.includes(ext)) {
                                          skip = true;
                                          break;
                                      }
                                  }
            }

            if (!skip) newLines.push(line);
        }
        return newLines.join('\r\n');
    };

    window.RTCPeerConnection = function(config) {
        console.log("[BxC] RTCPeerConnection constructor called", JSON.stringify(config));
        window.__labNativeActive = true;
        try { emit("native_pc_created", "yes"); } catch (e) { }

        if (window.AndroidBridge && config) {
            window.AndroidBridge.onPeerConnectionConfig(JSON.stringify(config));
        }

        const pc = {
            config: config,
            localDescription: null,
            remoteDescription: null,
            connectionState: 'new',
            iceConnectionState: 'new',
            signalingState: 'stable',
            _listeners: {},
            _transceivers: [],

            createDataChannel: function(label, options) {
                console.log("[BxC] Proxy createDataChannel: " + label + " options: " + JSON.stringify(options));
                if (window.AndroidBridge) {
                    window.AndroidBridge.onDataChannelCreate(label);
                }

                const dc = {
                    label: label,
                    id: options ? options.id : null,
                    ordered: options ? options.ordered : true,
                    protocol: options ? (options.protocol || "") : "",
                    readyState: 'connecting',
                    binaryType: 'arraybuffer',
                    onmessage: null,
                    onopen: null,
                    onclose: null,

                   send: function(data) {
                                           if(label=='input'||label=='unreliableinput'||label=='reliableinput')return;
                                           if (window.AndroidBridge) {
                                               if(label=='message'&&!data.includes('Handshake')){return;}
                                               let base64;
                                               let isBinary = typeof data !== 'string';
                                               if (isBinary) {

                                                       window.AndroidBridge.onDataChannelSend(label, new Uint8Array(data), null, true);
                                                       return;

                                               } else {
                                               if(label=='control'&&data.includes('resolutionAlias')){
                                               let overridesData=JSON.parse(data);
                                               overridesData.resolutionAlias=window.BX_TARGET_RES;
                                               data=JSON.stringify(overridesData);
                                               }
                                               console.log('sending data from channel'+label+': '+data);
                                               base64 = window.btoa(unescape(encodeURIComponent(data)));
                                               window.AndroidBridge.onDataChannelSend(label, null, base64, false);

                                           }}
                                       },
                    close: function() {
                        console.log("[BxC] Proxy DataChannel close: " + label);
                    },
                    addEventListener: function(type, listener) {
                        if (!this._listeners) this._listeners = {};
                        if (!this._listeners[type]) this._listeners[type] = [];
                        this._listeners[type].push(listener);
                    },
                    removeEventListener: function(type, listener) {
                        if (this._listeners && this._listeners[type]) {
                            this._listeners[type] = this._listeners[type].filter(l => l !== listener);
                        }
                    },
                    dispatchEvent: function(event) {
                        if (event.type === 'message') {
                            if (this.onmessage) this.onmessage(event);
                            if (this._listeners && this._listeners['message']) {
                                this._listeners['message'].forEach(l => l(event));
                            }
                        }
                    }
                };

                if (!window.proxyDataChannels) window.proxyDataChannels = {};
                window.proxyDataChannels[label] = dc;

                return dc;
            },

            addTransceiver: function(trackOrKind, init) {
                console.log("[BxC] Proxy addTransceiver: " + trackOrKind);
                if (window.AndroidBridge) {
                    window.AndroidBridge.onAddTransceiver(trackOrKind, init ? (init.direction || "recvonly") : "recvonly");
                }
                const transceiver = {
                    mid: null,
                    direction: init ? (init.direction || 'sendrecv') : 'sendrecv',
                    sender: { track: (typeof trackOrKind !== 'string' ? trackOrKind : null) },
                    receiver: { track: { kind: (typeof trackOrKind === 'string' ? trackOrKind : trackOrKind.kind), stop: () => {} } },
                    stop: () => {},
                    setCodecPreferences: function(codecs) { console.log("[BxC] Proxy setCodecPreferences"); }
                };
                this._transceivers.push(transceiver);
                return transceiver;
            },

            addTrack: function(track, ...streams) {
                console.log("[BxC] Proxy addTrack: " + track.kind);
                return { track: track };
            },

            getTransceivers: function() { return this._transceivers || []; },
            getReceivers: function() { return (this._transceivers || []).map(t => t.receiver); },
            getSenders: function() { return (this._transceivers || []).map(t => t.sender); },

            setRemoteDescription: function(description) {
                console.log("[BxC] Proxy setRemoteDescription: " + description.type);
                this.remoteDescription = description;
                if (description && window.AndroidBridge) {
                    if (description.type === 'offer') {
                        window.AndroidBridge.onOfferReceived(description.sdp);
                    } else if (description.type === 'answer') {
                        window.AndroidBridge.onAnswerReceived(description.sdp);
                    }
                }
                return Promise.resolve();
            },

            createAnswer: function() {
                console.log("[BxC] Proxy createAnswer");
                return new Promise((resolve) => {
                    window.pendingAnswerResolver = (answer) => {
                        this.localDescription = answer;
                        resolve(answer);
                    };
                });
            },

            createOffer: function() {
                            console.log("[BxC] Proxy createOffer requested");
                            return new Promise((resolve) => {
                                window.pendingOfferResolver = (offer) => {
                                    const bitrateMbps = getTargetBitrate();
                                    if (bitrateMbps > 0) {
                                        try {
                                            // Convert Mbps to Kbps for SDP (b=AS line)
                                            const bitrateKbps = bitrateMbps * 1000;
                                            offer.sdp = patchSdpBitrate(offer.sdp, bitrateKbps);
                                            BxLogger.info("Patcher", "Applied bitrate patch:", bitrateMbps + " Mbps");
                                        } catch (e) {
                                            BxLogger.error("Patcher", "Bitrate patch failed", e);
                                        }
                                    }

                                    offer.sdp = patchSdpFps(offer.sdp, 60);
                                    this.localDescription = offer;
                                    console.log("[BxC] Sending offer to server, length: " + offer.sdp.length);
                                    resolve(offer);
                                };
                                if (window.AndroidBridge) {
                                    window.AndroidBridge.onOfferRequested();
                                }
                            });
                        },

           setLocalDescription: function(description) {
               console.log("[BxC] Proxy setLocalDescription: " + (description ? description.type : "null"));
               this.localDescription = description;

               // 1. Update the internal state
               this.signalingState = description.type === 'offer' ? 'have-local-offer' : 'stable';

               // 2. Fire the state change event
               let event = new Event('signalingstatechange');
               if (this.onsignalingstatechange) this.onsignalingstatechange(event);
               if (this._listeners && this._listeners['signalingstatechange']) {
                   this._listeners['signalingstatechange'].forEach(l => l(event));
               }

               return Promise.resolve();
           },

            setConfiguration: function(config) {
                console.log("[BxC] Proxy setConfiguration", JSON.stringify(config));
                this.config = config;
                if (window.AndroidBridge && config) {
                    window.AndroidBridge.onPeerConnectionConfig(JSON.stringify(config));
                }
            },

            addIceCandidate: function(candidate) {
                console.log("[BxC] Proxy addIceCandidate");
                if (candidate && window.AndroidBridge) {
                    window.AndroidBridge.onIceCandidateReceived(candidate.sdpMid, candidate.sdpMLineIndex, candidate.candidate || candidate.sdp || "");
                }
                return Promise.resolve();
            },

            addEventListener: function(type, listener) {
                if (!this._listeners[type]) this._listeners[type] = [];
                this._listeners[type].push(listener);
                this['on' + type] = listener;
            },

            getStats: function() {
                return Promise.resolve(new Map());
            },

            close: function() {
                console.log("[BxC] Proxy close");
                if (window.AndroidBridge) {
                    window.AndroidBridge.onPeerConnectionClose();
                }
            }
        };

        window.peer = pc;
        return pc;
    };

    window.RTCPeerConnection.prototype = OrgRTCPeerConnection.prototype;
    if (OrgRTCPeerConnection.generateCertificate) {
        window.RTCPeerConnection.generateCertificate = OrgRTCPeerConnection.generateCertificate.bind(OrgRTCPeerConnection);
    }
}
    try { patchRtcPeerConnection(); } catch (e) { emit('native_shim_failed', scrub(e && e.message)); }

    var ofetch = window.fetch;
    function loggedFetch(input, init) {
      var rawUrl = '';
      try { rawUrl = String((typeof input === 'string') ? input : (input && input.url)); } catch (e) { }
      var p = ofetch.apply(this, arguments);
      if (EXP_URL.test(rawUrl)) return p.then(patchExperimentation);
      return p;
    }
    var INTERCEPTED_SUFFIXES = ['/v2/login/user', '/sessions/cloud/play', '/configuration'];
    function interceptedSuffix(urlStr) {
      try {
        if (!/xboxlive\.com$/i.test(new URL(urlStr, location.href).hostname)) return null;
        var p = new URL(urlStr, location.href).pathname;
        for (var i = 0; i < INTERCEPTED_SUFFIXES.length; i++) { if (p.endsWith(INTERCEPTED_SUFFIXES[i])) return INTERCEPTED_SUFFIXES[i]; }
      } catch (e) { }
      return null;
    }
    var NATIVE_FETCH = ofetch;  // used by the ported interceptor, same meaning as in the proven build
    if (ofetch) {
      window.fetch = function (input, init) {
        var self = this;
        var rawUrl = '';
        try { rawUrl = String((typeof input === 'string') ? input : (input && input.url)); } catch (e) { }
        var suf = interceptedSuffix(rawUrl);
        if (suf) {
          var req = (typeof Request === 'function' && input instanceof Request) ? input : new Request(input, init);
          emit('native_intercept', suf);
          return XcloudInterceptor.handle(req, init).catch(function (e) { emit('native_intercept_failed', suf + ' ' + scrub(e && e.name)); return NATIVE_FETCH(req, init); });
        }
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
