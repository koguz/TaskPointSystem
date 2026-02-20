(function () {
  'use strict';

  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    return;
  }

  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var rawData = atob(base64);
    var outputArray = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; i++) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  function getCsrfToken() {
    var cookie = document.cookie.split(';').find(function (c) {
      return c.trim().startsWith('csrftoken=');
    });
    return cookie ? cookie.split('=')[1] : '';
  }

  var swRegistration = null;

  function registerServiceWorker() {
    return navigator.serviceWorker.register('/sw.js').then(function (reg) {
      swRegistration = reg;
      return reg;
    });
  }

  function getVapidPublicKey() {
    return fetch('/api/push/vapid-key/')
      .then(function (r) { return r.json(); })
      .then(function (data) { return data.publicKey; });
  }

  function subscribePush(vapidKey) {
    var applicationServerKey = urlBase64ToUint8Array(vapidKey);
    return swRegistration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: applicationServerKey
    });
  }

  function sendSubscriptionToServer(subscription) {
    return fetch('/api/push/subscribe/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify(subscription.toJSON())
    });
  }

  function sendUnsubscribeToServer(endpoint) {
    return fetch('/api/push/unsubscribe/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({ endpoint: endpoint })
    });
  }

  function updatePushStatusUI(state) {
    var statusEl = document.getElementById('push-status');
    var enableBtn = document.getElementById('push-enable-btn');
    var disableBtn = document.getElementById('push-disable-btn');
    var bellBtn = document.getElementById('push-bell-btn');

    if (statusEl) {
      if (state === 'enabled') {
        statusEl.textContent = 'Enabled';
        statusEl.className = 'badge bg-success';
      } else if (state === 'blocked') {
        statusEl.textContent = 'Blocked by Browser';
        statusEl.className = 'badge bg-danger';
      } else {
        statusEl.textContent = 'Disabled';
        statusEl.className = 'badge bg-secondary';
      }
    }

    if (enableBtn) enableBtn.style.display = (state === 'disabled') ? '' : 'none';
    if (disableBtn) disableBtn.style.display = (state === 'enabled') ? '' : 'none';

    if (bellBtn) {
      if (state === 'enabled') {
        bellBtn.classList.add('text-warning');
        bellBtn.title = 'Notifications enabled';
      } else {
        bellBtn.classList.remove('text-warning');
        bellBtn.title = 'Enable notifications';
      }
    }
  }

  function checkCurrentState() {
    if (!swRegistration) return;
    if (Notification.permission === 'denied') {
      updatePushStatusUI('blocked');
      return;
    }
    swRegistration.pushManager.getSubscription().then(function (sub) {
      updatePushStatusUI(sub ? 'enabled' : 'disabled');
    });
  }

  window.tpsEnablePush = function () {
    registerServiceWorker()
      .then(function () { return getVapidPublicKey(); })
      .then(function (key) { return subscribePush(key); })
      .then(function (sub) { return sendSubscriptionToServer(sub); })
      .then(function () { updatePushStatusUI('enabled'); })
      .catch(function (err) {
        console.error('Push subscription failed:', err);
        if (Notification.permission === 'denied') {
          updatePushStatusUI('blocked');
        }
      });
  };

  window.tpsDisablePush = function () {
    if (!swRegistration) return;
    swRegistration.pushManager.getSubscription().then(function (sub) {
      if (!sub) {
        updatePushStatusUI('disabled');
        return;
      }
      var endpoint = sub.endpoint;
      sub.unsubscribe().then(function () {
        return sendUnsubscribeToServer(endpoint);
      }).then(function () {
        updatePushStatusUI('disabled');
      });
    });
  };

  registerServiceWorker().then(function () {
    checkCurrentState();
  }).catch(function (err) {
    console.warn('Service worker registration failed:', err);
  });
})();
