import React, { useState, useEffect } from 'react';
import { notificationsAPI, analyticsAPI } from '../api';
import PushNotificationToggle from './PushNotificationToggle';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

const Dashboard = () => {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Form state
  const [facilityInput, setFacilityInput] = useState('');
  const [facilityName, setFacilityName] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [notifyEmail, setNotifyEmail] = useState(true);
  const [notifySms, setNotifySms] = useState(false);
  const [notifyPush, setNotifyPush] = useState(true);
  const [minNights, setMinNights] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  
  // Analytics state
  const [selectedFacility, setSelectedFacility] = useState(null);
  const [analyticsData, setAnalyticsData] = useState(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);

  useEffect(() => {
    fetchNotifications();
  }, []);

  const fetchNotifications = async () => {
    try {
      const response = await notificationsAPI.getAll();
      setNotifications(response.data);
    } catch (err) {
      setError('Failed to load notifications');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setSubmitting(true);

    try {
      await notificationsAPI.create({
        facility_id: facilityInput,
        facility_name: facilityName,
        start_date: startDate,
        end_date: endDate,
        notify_email: notifyEmail,
        notify_sms: notifySms,
        notify_push: notifyPush,
        min_nights: minNights,
      });

      setSuccess('Notification request created successfully!');
      setFacilityInput('');
      setFacilityName('');
      setStartDate('');
      setEndDate('');
      setMinNights(1);
      fetchNotifications();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create notification request');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this notification request?')) {
      return;
    }

    try {
      await notificationsAPI.delete(id);
      setSuccess('Notification request deleted');
      fetchNotifications();
    } catch (err) {
      setError('Failed to delete notification request');
    }
  };

  const handleToggleNotification = async (id, field, currentValue) => {
    try {
      await notificationsAPI.update(id, { [field]: !currentValue });
      fetchNotifications();
    } catch (err) {
      setError('Failed to update notification preferences');
    }
  };

  const loadAnalytics = async (facilityId, facilityName) => {
    setSelectedFacility({ id: facilityId, name: facilityName });
    setLoadingAnalytics(true);
    try {
      const response = await analyticsAPI.getFacilityAnalytics(facilityId);
      setAnalyticsData(response.data);
    } catch (err) {
      console.error('Failed to load analytics:', err);
      setAnalyticsData(null);
    } finally {
      setLoadingAnalytics(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <div className="container">
      <div className="page-header">
        <h2>🏕️ Campsite Availability Tracker</h2>
        <p>Monitor your favorite campsites and get notified when spots become available</p>
      </div>
      {/* Push Notification Settings */}
      <PushNotificationToggle />
      {/* Add New Campsite Form */}
      <div className="card">
        <h3>➕ Add Campsite Monitor</h3>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Campsite URL or ID</label>
            <input
              type="text"
              value={facilityInput}
              onChange={(e) => setFacilityInput(e.target.value)}
              required
              placeholder="https://www.recreation.gov/camping/campgrounds/232447 or just 232447"
            />
            <small style={{ color: '#666', fontSize: '12px' }}>
              Enter the Recreation.gov campground URL or facility ID
            </small>
          </div>
          <div className="form-group">
            <label>Campground Name (Optional)</label>
            <input
              type="text"
              value={facilityName}
              onChange={(e) => setFacilityName(e.target.value)}
              placeholder="e.g., Yosemite National Park"
            />
          </div>
          <div style={{ display: 'flex', gap: '16px' }}>
            <div className="form-group" style={{ flex: 1 }}>
              <label>Start Date</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                required
              />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label>End Date</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                required
              />
            </div>
          </div>
          <div className="form-group">
            <label>Minimum Consecutive Nights</label>
            <input
              type="number"
              value={minNights}
              onChange={(e) => setMinNights(Math.max(1, parseInt(e.target.value) || 1))}
              min="1"
              required
            />
            <small style={{ color: '#666', fontSize: '0.875rem', marginTop: '4px', display: 'block' }}>
              Campsite must have at least this many consecutive nights available
            </small>
          </div>
          <div className="checkbox-group">
            <input
              type="checkbox"
              id="notify-email"
              checked={notifyEmail}
              onChange={(e) => setNotifyEmail(e.target.checked)}
            />
            <label htmlFor="notify-email">📧 Email Notifications</label>
          </div>
          <div className="checkbox-group">
            <input
              type="checkbox"
              id="notify-sms"
              checked={notifySms}
              onChange={(e) => setNotifySms(e.target.checked)}
            />
            <label htmlFor="notify-sms">📱 SMS Notifications</label>
          </div>
          <div className="checkbox-group">
            <input
              type="checkbox"
              id="notify-push"
              checked={notifyPush}
              onChange={(e) => setNotifyPush(e.target.checked)}
            />
            <label htmlFor="notify-push">🔔 Push Notifications</label>
          </div>
          {error && <div className="alert alert-error">⚠️ {error}</div>}
          {success && <div className="alert alert-success">✓ {success}</div>}
          <button type="submit" className="btn btn-primary btn-lg" disabled={submitting} style={{ marginTop: '0.5rem' }}>
            {submitting ? '⏳ Adding...' : '➕ Start Monitoring'}
          </button>
        </form>
      </div>

      {/* Active Notifications List */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ margin: 0 }}>📍 Your Monitored Campsites</h3>
          <span className="badge badge-secondary">{notifications.length} active</span>
        </div>
        {notifications.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🏕️</div>
            <h3>No campsites being monitored</h3>
            <p>Add your first campsite above to start receiving availability notifications</p>
          </div>
        ) : (
          notifications.map((notification) => (
            <div key={notification.id} className="notification-item">
              <h3>
                <a 
                  href={`https://www.recreation.gov/camping/campgrounds/${notification.facility_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    color: 'inherit',
                    textDecoration: 'none',
                    borderBottom: '2px solid var(--primary-color)',
                    transition: 'color 0.2s'
                  }}
                  onMouseEnter={(e) => e.target.style.color = 'var(--primary-color)'}
                  onMouseLeave={(e) => e.target.style.color = 'inherit'}
                >
                  {notification.facility_name}
                </a>
              </h3>
              <div className="meta">
                <strong>Facility ID:</strong> {notification.facility_id}
              </div>
              <div className="meta">
                <strong>Dates:</strong> {notification.start_date} to {notification.end_date}
              </div>
              <div className="meta">
                <strong>Minimum Nights:</strong> {notification.min_nights || 1}
              </div>
              
              {/* Availability Status */}
              <div style={{ 
                margin: '1rem 0',
                padding: '1rem',
                backgroundColor: notification.last_available_count > 0 ? 'var(--success-bg)' : 'var(--background)',
                border: `2px solid ${notification.last_available_count > 0 ? 'var(--success-color)' : 'var(--border-color)'}`,
                borderRadius: 'var(--radius-md)',
                display: 'flex',
                alignItems: 'center',
                gap: '1rem'
              }}>
                <div style={{ fontSize: '2rem' }}>
                  {notification.last_available_count > 0 ? '✅' : '⏳'}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                    Current Availability
                  </div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700, color: notification.last_available_count > 0 ? 'var(--success-color)' : 'var(--text-secondary)' }}>
                    {notification.last_available_count !== undefined && notification.last_available_count !== null
                      ? `${notification.last_available_count} site${notification.last_available_count !== 1 ? 's' : ''} available`
                      : 'Checking...'}
                  </div>
                  {notification.available_dates && notification.available_dates.length > 0 && (
                    <div style={{ fontSize: '0.875rem', color: 'var(--text-primary)', marginTop: '0.5rem', padding: '0.5rem', backgroundColor: 'rgba(40, 167, 69, 0.1)', borderRadius: '4px' }}>
                      <strong>📅 Available dates:</strong> {notification.available_dates.slice(0, 5).map(date => new Date(date).toLocaleDateString()).join(', ')}
                      {notification.available_dates.length > 5 && ` (+${notification.available_dates.length - 5} more)`}
                    </div>
                  )}
                  {notification.last_checked && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                      Last checked: {new Date(notification.last_checked).toLocaleString()}
                    </div>
                  )}
                </div>
              </div>
              
              <div className="meta">
                <strong>Last Notified:</strong>{' '}
                {notification.last_notified
                  ? new Date(notification.last_notified).toLocaleString()
                  : 'Never'}
              </div>
              <div style={{ marginTop: '12px' }}>
                <div className="checkbox-group">
                  <input
                    type="checkbox"
                    id={`email-${notification.id}`}
                    checked={notification.notify_email}
                    onChange={() =>
                      handleToggleNotification(
                        notification.id,
                        'notify_email',
                        notification.notify_email
                      )
                    }
                  />
                  <label htmlFor={`email-${notification.id}`}>📧 Email</label>
                </div>
                <div className="checkbox-group">
                  <input
                    type="checkbox"
                    id={`sms-${notification.id}`}
                    checked={notification.notify_sms}
                    onChange={() =>
                      handleToggleNotification(
                        notification.id,
                        'notify_sms',
                        notification.notify_sms
                      )
                    }
                  />
                  <label htmlFor={`sms-${notification.id}`}>📱 SMS</label>
                </div>
                <div className="checkbox-group">
                  <input
                    type="checkbox"
                    id={`push-${notification.id}`}
                    checked={notification.notify_push !== false}
                    onChange={() =>
                      handleToggleNotification(
                        notification.id,
                        'notify_push',
                        notification.notify_push !== false
                      )
                    }
                  />
                  <label htmlFor={`push-${notification.id}`}>🔔 Push</label>
                </div>
              </div>
              <div className="actions">
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => loadAnalytics(notification.facility_id, notification.facility_name)}
                >
                  📊 View Analytics
                </button>
                <button
                  className="btn btn-danger btn-sm"
                  onClick={() => handleDelete(notification.id)}
                >
                  🗑️ Remove
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Analytics Section */}
      {selectedFacility && (
        <div className="card">
          <h3>📊 Availability Analytics</h3>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
            {selectedFacility.name}
          </p>
          {loadingAnalytics ? (
            <div className="loading">Loading analytics</div>
          ) : analyticsData && analyticsData.weekly_stats.length > 0 ? (
            <>
              <div className="alert alert-info" style={{ marginBottom: '1.5rem' }}>
                ℹ️ This chart shows how many times campsites became available each week (reserved → available)
              </div>
              <ResponsiveContainer width="100%" height={350}>
                <LineChart data={analyticsData.weekly_stats}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                  <XAxis
                    dataKey="week_number"
                    label={{ value: 'Week of Year', position: 'insideBottom', offset: -5 }}
                    stroke="var(--text-secondary)"
                  />
                  <YAxis
                    label={{ value: 'Availability Changes', angle: -90, position: 'insideLeft' }}
                    stroke="var(--text-secondary)"
                  />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="availability_changes"
                    stroke="var(--primary-color)"
                    strokeWidth={2}
                    name="Times Became Available"
                    dot={{ fill: 'var(--primary-color)', r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </>
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon">📈</div>
              <h3>No analytics data yet</h3>
              <p>Historical data will appear after monitoring this campground for a while</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Dashboard;
