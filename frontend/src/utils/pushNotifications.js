import axios from 'axios';

// Use dynamic API URL to support mobile devices and production
const getApiUrl = () => {
  if (process.env.REACT_APP_API_URL) {
    return `${process.env.REACT_APP_API_URL}/api`;
  }
  
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    return `${protocol}//${hostname}:8000/api`;
  }
  return 'http://localhost:8000/api';
};

const API_URL = getApiUrl();

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
  const hasServiceWorker = 'serviceWorker' in navigator;
  const hasPushManager = 'PushManager' in window;
  const isSecureContext = window.isSecureContext || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  
  console.log('Push support check:', { hasServiceWorker, hasPushManager, isSecureContext });
  
  return hasServiceWorker && hasPushManager && isSecureContext;
}

/**
 * Get detailed information about why push might not be supported
 */
export function getPushSupportInfo() {
  const hasServiceWorker = 'serviceWorker' in navigator;
  const hasPushManager = 'PushManager' in window;
  const isSecureContext = window.isSecureContext || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  
  let message = '';
  if (!hasServiceWorker) {
    message = 'Service Workers are not supported in this browser.';
  } else if (!hasPushManager) {
    message = 'Push notifications are not supported in this browser.';
  } else if (!isSecureContext) {
    message = 'Push notifications require HTTPS. Please access the site using https:// or use localhost for testing.';
  } else {
    message = 'Push notifications are supported!';
  }
  
  return {
    supported: hasServiceWorker && hasPushManager && isSecureContext,
    hasServiceWorker,
    hasPushManager,
    isSecureContext,
    message
  };
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
  console.log('subscribeToPushNotifications: Starting...');
  
  const supportInfo = getPushSupportInfo();
  console.log('subscribeToPushNotifications: Support info:', supportInfo);
  
  if (!supportInfo.supported) {
    throw new Error(supportInfo.message);
  }
  console.log('subscribeToPushNotifications: Push is supported');

  // Request permission first
  console.log('subscribeToPushNotifications: Requesting permission...');
  const permission = await requestNotificationPermission();
  console.log('subscribeToPushNotifications: Permission result:', permission);
  
  if (permission !== 'granted') {
    throw new Error('Notification permission denied');
  }

  // Register service worker
  console.log('subscribeToPushNotifications: Registering service worker...');
  const registration = await registerServiceWorker();
  console.log('subscribeToPushNotifications: Service worker registered');

  // Get VAPID public key
  console.log('subscribeToPushNotifications: Fetching VAPID key...');
  const vapidPublicKey = await getVapidPublicKey(token);
  console.log('subscribeToPushNotifications: VAPID key received:', vapidPublicKey?.substring(0, 20) + '...');
  
  const convertedKey = urlBase64ToUint8Array(vapidPublicKey);

  // Subscribe to push notifications
  console.log('subscribeToPushNotifications: Subscribing to push manager...');
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: convertedKey
  });
  console.log('subscribeToPushNotifications: Push subscription created');

  // Send subscription to backend
  console.log('subscribeToPushNotifications: Sending subscription to backend...');
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
  console.log('subscribeToPushNotifications: Backend response:', response.data);

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
    // Check if service worker is registered first
    const registration = await navigator.serviceWorker.getRegistration();
    if (!registration) {
      console.log('No service worker registered yet');
      return false;
    }
    
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
    // Check if service worker is registered first
    const registration = await navigator.serviceWorker.getRegistration();
    if (!registration) {
      return null;
    }
    
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
