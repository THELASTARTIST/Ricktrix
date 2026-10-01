// RICKTRIX API client -- opt-in bridge to the backend.
//
// NOT loaded by any page yet. Adding one line to a page switches it from the
// hardcoded arrays in autofare.js to the API, and every function here falls
// back to those same arrays if the server is unreachable, so the site keeps
// working offline, from the filesystem, and with the backend down.
//
// To enable on a page, add this immediately after data.js:
//
//   <script src="api.js"></script>
//
// and set the base URL if the API is not on the same origin:
//
//   <script>window.RICKTRIX_API = 'http://localhost:8000';</script>
//
// Then swap `autorouteRoutes` for `await RICKTRIX.routes()` and so on. See
// backend/README.md for the per-file recipe.

(function (global) {
  'use strict';

  // Same origin by default, which is what you want in production: the API and
  // the site are served by the same FastAPI process, so there is no CORS and no
  // second URL to configure. localhost:8000 is only the development fallback,
  // for when you are running the pages from a plain static server.
  function defaultBase() {
    var loc = global.location || {};
    if (loc.protocol === 'http:' || loc.protocol === 'https:') {
      return loc.origin;
    }
    return 'http://localhost:8000';
  }

  var BASE = global.RICKTRIX_API || defaultBase();
  var TIMEOUT_MS = 4000;
  var cache = {};

  // Local fallback, so every call below can degrade instead of throwing.
  function localRoutes() {
    return global.autorouteRoutes || [];
  }

  function request(path, options) {
    var settings = options || {};
    var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timer = setTimeout(function () { if (controller) controller.abort(); }, TIMEOUT_MS);

    // Merge caller headers (Authorization) with our own Content-Type, so an
    // authenticated call is not silently sent without its token.
    var headers = {};
    if (settings.headers) {
      Object.keys(settings.headers).forEach(function (key) {
        headers[key] = settings.headers[key];
      });
    }
    if (settings.body) headers['Content-Type'] = 'application/json';

    return fetch(BASE + path, {
      method: settings.method || 'GET',
      headers: headers,
      body: settings.body ? JSON.stringify(settings.body) : undefined,
      signal: controller ? controller.signal : undefined
    })
      .then(function (response) {
        clearTimeout(timer);
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.json();
      })
      .catch(function (error) {
        clearTimeout(timer);
        // Surface the reason once, then carry on with local data.
        if (!global.RICKTRIX_API_QUIET) console.warn('[RICKTRIX] API unavailable, using local data:', error.message);
        return null;
      });
  }

  function memo(key, loader) {
    if (!(key in cache)) cache[key] = loader();
    return cache[key];
  }

  // Merged, not assigned. pwa.js also builds a `RICKTRIX` namespace and is
  // loaded with `defer` on every page, so a plain assignment here would replace
  // that object wholesale and take install()/canInstall() with it.
  global.RICKTRIX = Object.assign(global.RICKTRIX || {}, {
    base: function () { return BASE; },

    // GET /api/routes -> {routes, total, ...}
    routes: function (params) {
      var query = new URLSearchParams(params || {}).toString();
      return request('/api/routes' + (query ? '?' + query : ''))
        .then(function (body) {
          return body ? body.routes : localRoutes();
        });
    },

    // GET /api/stops?q=how -> [{name, count}]
    stops: function (q, limit) {
      var query = new URLSearchParams({ q: q || '', limit: limit || 8 }).toString();
      return request('/api/stops?' + query)
        .then(function (body) {
          if (body) return body;
          var needle = (q || '').toLowerCase();
          var seen = {};
          localRoutes().forEach(function (r) {
            [r.from, r.to].concat(r.via || []).forEach(function (n) {
              if (n && n.toLowerCase().indexOf(needle) === 0) seen[n] = (seen[n] || 0) + 1;
            });
          });
          return Object.keys(seen).slice(0, limit || 8).map(function (name) {
            return { name: name, count: seen[name] };
          });
        });
    },

    // GET /api/stats -> real counts, so nothing has to hardcode "450+"
    stats: function () {
      return memo('stats', function () {
        return request('/api/stats').then(function (body) {
          return body || { routes: localRoutes().length, source: 'local' };
        });
      });
    },

    // POST /api/predict/fare -> {fare_inr, source: 'observed'|'estimated', ...}
    // Resolves to null rather than guessing when the server is down.
    fare: function (from, to, viaCount) {
      return request('/api/predict/fare', {
        method: 'POST',
        body: { from: from, to: to, via_count: viaCount || 0 }
      });
    },

    // POST /api/submissions -> {id, status, message}
    submitRoute: function (from, to, fare, note) {
      return request('/api/submissions', {
        method: 'POST',
        body: { from: from, to: to, fare_inr: fare || null, note: note || null }
      });
    },

    // Replaces the localStorage round-trip in index.html / all_routes.html /
    // saved_routes.html. Without a session this is a no-op and the caller
    // keeps using rictrix-saved exactly as before.
    syncBookmarks: function (token) {
      return request('/api/bookmarks', {
        headers: { Authorization: 'Bearer ' + token }
      }).then(function (body) { return body ? body.routes : null; });
    }
  });
})(window);
