/* RICKTRIX PWA registration.
 *
 * Loaded by every page. Three jobs:
 *   1. register the service worker so the app installs and works offline
 *   2. tell the user when a new version is ready, instead of silently swapping
 *   3. capture the install prompt so you can put an "Install app" button
 *      anywhere, rather than relying on the browser's own UI
 *
 * Exposes:
 *   RICKTRIX.install()        -> true if the install sheet was opened
 *   RICKTRIX.canInstall()     -> bool
 *   RICKTRIX.onInstall(cb)    -> cb fires once installed
 *   RICKTRIX.isInstalled()    -> true if already running standalone
 */

(function (global) {
  'use strict';

  var installPrompt = null;
  var installCallbacks = [];

  // --- install prompt ----------------------------------------------------

  global.addEventListener('beforeinstallprompt', function (event) {
    // Chrome fires this instead of showing its own mini-infobar. Preventing the
    // default is what lets us re-show the prompt later on request.
    event.preventDefault();
    installPrompt = event;
    document.dispatchEvent(new CustomEvent('ricktrix:installable'));
  });

  global.addEventListener('appinstalled', function () {
    installPrompt = null;
    installCallbacks.forEach(function (cb) { try { cb(); } catch (e) {} });
    installCallbacks = [];
  });

  // --- update flow ------------------------------------------------------

  function notifyUpdate(registration) {
    var banner = document.getElementById('ricktrix-update');
    if (banner) { banner.hidden = false; return; }
    // No banner in the markup: build a minimal one so every page gets it free.
    var el = document.createElement('div');
    el.id = 'ricktrix-update';
    el.setAttribute('role', 'status');
    el.style.cssText = [
      'position:fixed', 'left:50%', 'bottom:16px', 'transform:translateX(-50%)',
      'z-index:2147483647', 'display:flex', 'gap:12px', 'align-items:center',
      'background:#16130F', 'color:#F7F2E1', 'padding:12px 16px',
      'border-radius:12px', 'font:500 14px/1.3 system-ui,sans-serif',
      'box-shadow:0 8px 28px rgba(0,0,0,.32)', 'max-width:calc(100vw - 32px)'
    ].join(';');

    var text = document.createElement('span');
    text.textContent = 'A new version of RICKTRIX is ready.';

    var button = document.createElement('button');
    button.textContent = 'Reload';
    button.style.cssText = [
      'background:#FFC22E', 'color:#16130F', 'border:0', 'border-radius:8px',
      'padding:8px 14px', 'font:600 14px/1 system-ui,sans-serif', 'cursor:pointer'
    ].join(';');
    button.addEventListener('click', function () {
      if (registration.waiting) registration.waiting.postMessage('SKIP_WAITING');
      global.location.reload();
    });

    el.appendChild(text);
    el.appendChild(button);
    document.body.appendChild(el);
  }

  // --- registration -----------------------------------------------------

  function register() {
    if (!('serviceWorker' in global.navigator)) return;
    // file:// has no service worker support, and neither do insecure origins.
    // The page still works; it just cannot be installed or cached.
    if (global.location.protocol === 'file:') {
      console.info('[RICKTRIX] opened from the filesystem - offline install disabled. Serve over http://localhost or https:// instead.');
      return;
    }

    global.addEventListener('load', function () {
      global.navigator.serviceWorker.register('sw.js', { scope: './' })
        .then(function (registration) {
          if (registration.waiting && global.navigator.serviceWorker.controller) {
            notifyUpdate(registration);
          }
          registration.addEventListener('updatefound', function () {
            var installing = registration.installing;
            if (!installing) return;
            installing.addEventListener('statechange', function () {
              if (installing.state === 'installed' && global.navigator.serviceWorker.controller) {
                notifyUpdate(registration);
              }
            });
          });
        })
        .catch(function (error) {
          console.warn('[RICKTRIX] service worker failed to register:', error);
        });

      // Check for a new build when the app comes back to the foreground.
      document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'visible' && global.navigator.serviceWorker.controller) {
          global.navigator.serviceWorker.getRegistration().then(function (r) {
            if (r) r.update();
          });
        }
      });
    });
  }

  // --- install button ---------------------------------------------------
  //
  // Injected rather than written into six pages, so a new page gets it free
  // and there is one place to change the behaviour.

  // iOS has no beforeinstallprompt, so there is nothing to capture and the
  // button would never appear. What iOS does have is Share -> Add to Home
  // Screen, so that is what the button explains instead.
  function isIos() {
    return /iPad|iPhone|iPod/.test(global.navigator.userAgent)
      // iPadOS 13+ reports as a Mac; the touch-point count is the tell.
      || (global.navigator.platform === 'MacIntel' && global.navigator.maxTouchPoints > 1);
  }

  function needsIosInstructions() {
    return isIos() && !global.RICKTRIX.isInstalled();
  }

  function iosSheet() {
    // canInstall() is always false on iOS, so nothing consumes the event
    // that would otherwise stop a second sheet being opened on a second tap.
    var existing = document.getElementById('ricktrix-ios-help');
    if (existing) { existing.remove(); return; }

    var el = document.createElement('div');
    el.id = 'ricktrix-ios-help';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-label', 'How to install RICKTRIX');
    el.style.cssText = [
      'position:fixed', 'left:50%', 'bottom:16px', 'transform:translateX(-50%)',
      'z-index:2147483647', 'display:flex', 'gap:12px', 'align-items:center',
      'background:#16130F', 'color:#F7F2E1', 'padding:14px 16px',
      'border-radius:12px', 'font:500 14px/1.4 system-ui,sans-serif',
      'box-shadow:0 8px 28px rgba(0,0,0,.32)', 'max-width:calc(100vw - 32px)'
    ].join(';');

    var text = document.createElement('span');
    text.textContent = 'Tap the Share button, then "Add to Home Screen".';

    var close = document.createElement('button');
    close.textContent = 'Got it';
    close.style.cssText = [
      'background:#FFC22E', 'color:#16130F', 'border:0', 'border-radius:8px',
      'padding:8px 14px', 'font:600 14px/1 system-ui,sans-serif',
      'cursor:pointer', 'white-space:nowrap'
    ].join(';');
    close.addEventListener('click', function () { el.remove(); });

    el.appendChild(text);
    el.appendChild(close);
    document.body.appendChild(el);
  }

  function mountInstallButton() {
    if (document.getElementById('installBtn')) return;
    // The theme toggle is the last control in every header, so sitting just
    // before it keeps the button in the same place on all six pages.
    var anchor = document.getElementById('themeToggle')
      || document.querySelector('.headbar')
      || document.querySelector('header');
    if (!anchor) return;

    var button = document.createElement('button');
    button.id = 'installBtn';
    // Reuse the page's own button styling; .icon-btn is defined on all of them.
    button.className = anchor.className.indexOf('icon-btn') !== -1 ? 'icon-btn' : '';
    button.title = 'Install RICKTRIX';
    button.setAttribute('aria-label', 'Install RICKTRIX');
    button.style.display = 'none';
    button.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" '
      + 'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
      + 'stroke-linejoin="round"><path d="M12 3v12m0 0l-4.5-4.5M12 15l4.5-4.5"/>'
      + '<path d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"/></svg>';

    button.addEventListener('click', function () {
      if (global.RICKTRIX.canInstall()) {
        global.RICKTRIX.install().then(function (accepted) {
          if (!accepted) button.style.display = 'none';
        });
      } else {
        iosSheet();
      }
    });

    if (anchor.id === 'themeToggle') anchor.parentNode.insertBefore(button, anchor);
    else anchor.appendChild(button);

    refreshInstallButton();
  }

  function refreshInstallButton() {
    var button = document.getElementById('installBtn');
    if (!button) return;
    // Already installed, or the browser will not offer a prompt: nothing to
    // put in front of the user.
    var show = !global.RICKTRIX.isInstalled()
      && (global.RICKTRIX.canInstall() || needsIosInstructions());
    button.style.display = show ? '' : 'none';
  }

  // --- public surface ---------------------------------------------------

  global.RICKTRIX = global.RICKTRIX || {};

  global.RICKTRIX.install = function () {
    if (!installPrompt) return Promise.resolve(false);
    var prompt = installPrompt;
    installPrompt = null;
    return prompt.prompt()
      .then(function (outcome) { return outcome === 'accepted'; })
      .catch(function () { return false; });
  };

  global.RICKTRIX.canInstall = function () { return installPrompt !== null; };

  global.RICKTRIX.onInstall = function (callback) {
    if (typeof callback === 'function') installCallbacks.push(callback);
  };

  global.RICKTRIX.isInstalled = function () {
    return global.matchMedia('(display-mode: standalone)').matches
        || global.navigator.standalone === true;
  };

  // The browser can become installable long after load, so the button is
  // mounted immediately and revealed whenever that happens.
  document.addEventListener('ricktrix:installable', refreshInstallButton);
  global.addEventListener('appinstalled', refreshInstallButton);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mountInstallButton);
  } else {
    mountInstallButton();
  }

  register();
})(window);
