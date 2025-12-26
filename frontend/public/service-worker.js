/* eslint-disable no-restricted-globals */
// Service Worker for handling push notifications

self.addEventListener('install', (event) => {
  console.log('Service Worker installed');
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('Service Worker activated');
  event.waitUntil(self.clients.claim());
});

self.addEventListener('push', (event) => {
  console.log('Push notification received:', event);
  
  if (!event.data) {
    console.log('Push notification received but no data');
    return;
  }

  try {
    const data = event.data.json();
    console.log('Push notification data:', data);
    
    const title = data.title || 'Recreation.gov Notifier';
    const options = {
      body: data.body || 'New notification',
      icon: data.icon || '/logo192.png',
      badge: data.badge || '/logo192.png',
      vibrate: data.vibrate || [200, 100, 200],
      data: {
        url: data.data?.url || 'https://basecamp.highz.net',
        dateOfArrival: Date.now(),
      },
      actions: [
        {
          action: 'view',
          title: 'View Details',
          icon: '/logo192.png'
        },
        {
          action: 'close',
          title: 'Close',
          icon: '/logo192.png'
        }
      ],
      requireInteraction: true,
      tag: 'campsite-notification'
    };

    event.waitUntil(
      self.registration.showNotification(title, options)
    );
  } catch (error) {
    console.error('Error handling push notification:', error);
  }
});

self.addEventListener('notificationclick', (event) => {
  console.log('Notification clicked:', event.action);
  
  event.notification.close();

  if (event.action === 'close') {
    return;
  }

  // Default action or 'view' action - open the app
  const urlToOpen = event.notification.data?.url || 'https://basecamp.highz.net';

  event.waitUntil(
    self.clients.matchAll({
      type: 'window',
      includeUncontrolled: true
    }).then((clientList) => {
      // Check if there's already a window/tab open
      for (let i = 0; i < clientList.length; i++) {
        const client = clientList[i];
        if (client.url === urlToOpen && 'focus' in client) {
          return client.focus();
        }
      }
      // If not, open a new window/tab
      if (self.clients.openWindow) {
        return self.clients.openWindow(urlToOpen);
      }
    })
  );
});

self.addEventListener('notificationclose', (event) => {
  console.log('Notification closed:', event.notification.tag);
});
