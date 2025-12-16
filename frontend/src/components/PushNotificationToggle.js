import React, { useState, useEffect } from 'react';
import {
  isPushSupported,
  getNotificationPermission,
  subscribeToPushNotifications,
  unsubscribeFromPushNotifications,
  isPushSubscribed,
  sendTestPushNotification
} from '../utils/pushNotifications';

function PushNotificationToggle() {
  const [isSupported, setIsSupported] = useState(false);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [permission, setPermission] = useState('default');

  useEffect(() => {
    checkPushSupport();
  }, []);

  const checkPushSupport = async () => {
    setIsLoading(true);
    const supported = isPushSupported();
    setIsSupported(supported);

    if (supported) {
      const perm = getNotificationPermission();
      setPermission(perm);
      
      const subscribed = await isPushSubscribed();
      setIsSubscribed(subscribed);
    }
    
    setIsLoading(false);
  };

  const handleToggle = async () => {
    setError('');
    setSuccess('');
    setIsLoading(true);

    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('Not authenticated');
      }

      if (isSubscribed) {
        // Unsubscribe
        await unsubscribeFromPushNotifications(token);
        setIsSubscribed(false);
        setSuccess('Push notifications disabled');
      } else {
        // Subscribe
        await subscribeToPushNotifications(token);
        setIsSubscribed(true);
        setPermission('granted');
        setSuccess('Push notifications enabled! You\'ll receive alerts when campsites become available.');
      }
    } catch (err) {
      console.error('Error toggling push notifications:', err);
      setError(err.message || 'Failed to update push notification settings');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTestNotification = async () => {
    setError('');
    setSuccess('');
    setIsLoading(true);

    try {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('Not authenticated');
      }

      const result = await sendTestPushNotification(token);
      setSuccess(result.message || 'Test notification sent!');
    } catch (err) {
      console.error('Error sending test notification:', err);
      setError(err.response?.data?.detail || 'Failed to send test notification');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isSupported) {
    return (
      <div className="alert alert-info">
        <span className="alert-icon">ℹ️</span>
        <span>Push notifications are not supported in your browser.</span>
      </div>
    );
  }

  if (permission === 'denied') {
    return (
      <div className="alert alert-error">
        <span className="alert-icon">🚫</span>
        <div>
          <strong>Push notifications blocked</strong>
          <p>You've blocked notifications for this site. To enable them, please update your browser settings.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>🔔 Push Notifications</h3>
      
      <p style={{ color: 'var(--text-secondary)' }}>
        Receive instant browser notifications when campsites become available, even when this tab is closed.
      </p>

      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '15px' }}>
        <label className="switch">
          <input
            type="checkbox"
            checked={isSubscribed}
            onChange={handleToggle}
            disabled={isLoading}
          />
          <span className="slider"></span>
        </label>
        <span style={{ fontWeight: 500 }}>
          {isSubscribed ? '✅ Enabled' : '❌ Disabled'}
        </span>
      </div>

      {isSubscribed && (
        <button
          onClick={handleTestNotification}
          disabled={isLoading}
          className="btn btn-sm"
          style={{ marginBottom: '15px' }}
        >
          {isLoading ? 'Sending...' : '🧪 Send Test Notification'}
        </button>
      )}

      {error && (
        <div className="alert alert-error">
          <span className="alert-icon">❌</span>
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="alert alert-success">
          <span className="alert-icon">✅</span>
          <span>{success}</span>
        </div>
      )}
    </div>
  );
}

export default PushNotificationToggle;
