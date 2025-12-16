import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

/**
 * URL-safe base64 encode for VAPID key
 */
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

/**
 * Register service worker for push notifications
 */
export async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) {
    throw new Error('Service Workers are not supported in this browser');
  }

  try {
    const registration = await navigator.serviceWorker.register('/service-worker.js', {
      scope: '/'
    });
    console.log('Service Worker registered successfully:', registration);
    
    // Wait for the service worker to be ready
    await navigator.serviceWorker.ready;
    
    return registration;
  } catch (error) {
    console.error('Service Worker registration failed:', error);
    throw error;
  }
}

/**
 * Check if push notifications are supported
 */
export function isPushSupported() {
  return 'serviceWorker' in navigator && 'PushManager' in window;
}

/**
 * Get current notification permission status
 */
export function getNotificationPermission() {
  if (!('Notification' in window)) {
    return 'unsupported';
  }
  return Notification.permission;
}

/**
 * Request notification permission from user
 */
export async function requestNotificationPermission() {
  if (!('Notification' in window)) {
    throw new Error('Notifications are not supported in this browser');
  }

  const permission = await Notification.requestPermission();
  return permission;
}

/**
 * Get VAPID public key from backend
 */
async function getVapidPublicKey(token) {
  const response = await axios.get(`${API_URL}/push/vapid-public-key`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return response.data.publicKey;
}

/**
 * Subscribe to push notifications
 */
export async function subscribeToPushNotifications(token) {
  if (!isPushSupported()) {
    throw new Error('Push notifications are not supported');
  }

  // Request permission first
  const permission = await requestNotificationPermission();
  if (permission !== 'granted') {
    throw new Error('Notification permission denied');
  }

  // Register service worker
  const registration = await registerServiceWorker();

  // Get VAPID public key
  const vapidPublicKey = await getVapidPublicKey(token);
  const convertedKey = urlBase64ToUint8Array(vapidPublicKey);

  // Subscribe to push notifications
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: convertedKey
  });

  // Send subscription to backend
  const response = await axios.post(
    `${API_URL}/push/subscribe`,
    subscription.toJSON(),
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    }
  );

  return response.data;
}

/**
 * Unsubscribe from push notifications
 */
export async function unsubscribeFromPushNotifications(token) {
  if (!isPushSupported()) {
    return;
  }

  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();

    if (subscription) {
      // Unsubscribe from push manager
      await subscription.unsubscribe();

      // Remove subscription from backend
      await axios.delete(`${API_URL}/push/unsubscribe`, {
        params: { endpoint: subscription.endpoint },
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
    }
  } catch (error) {
    console.error('Error unsubscribing from push notifications:', error);
    throw error;
  }
}

/**
 * Check if currently subscribed to push notifications
 */
export async function isPushSubscribed() {
  if (!isPushSupported()) {
    return false;
  }

  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    return subscription !== null;
  } catch (error) {
    console.error('Error checking push subscription:', error);
    return false;
  }
}

/**
 * Get current push subscription
 */
export async function getPushSubscription() {
  if (!isPushSupported()) {
    return null;
  }

  try {
    const registration = await navigator.serviceWorker.ready;
    return await registration.pushManager.getSubscription();
  } catch (error) {
    console.error('Error getting push subscription:', error);
    return null;
  }
}

/**
 * Send a test push notification
 */
export async function sendTestPushNotification(token) {
  const response = await axios.post(
    `${API_URL}/push/test`,
    {},
    {
      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  );
  return response.data;
}
