import React, { useState, useEffect } from 'react';
import { notificationsAPI, analyticsAPI } from '../api';
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
      <h2>Dashboard</h2>

      {/* Add New Campsite Form */}
      <div className="card">
        <h3>Add New Campsite Notification</h3>
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
            <label htmlFor="notify-email">Email Notifications</label>
          </div>
          <div className="checkbox-group">
            <input
              type="checkbox"
              id="notify-sms"
              checked={notifySms}
              onChange={(e) => setNotifySms(e.target.checked)}
            />
            <label htmlFor="notify-sms">SMS Notifications</label>
          </div>
          {error && <div className="error">{error}</div>}
          {success && <div className="success">{success}</div>}
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? 'Adding...' : 'Add Notification Request'}
          </button>
        </form>
      </div>

      {/* Active Notifications List */}
      <div className="card">
        <h3>Active Notification Requests ({notifications.length})</h3>
        {notifications.length === 0 ? (
          <p style={{ color: '#666' }}>No active notification requests. Add one above to get started!</p>
        ) : (
          notifications.map((notification) => (
            <div key={notification.id} className="notification-item">
              <h3>{notification.facility_name}</h3>
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
                margin: '12px 0',
                padding: '12px',
                backgroundColor: notification.last_available_count > 0 ? '#d4edda' : '#f8f9fa',
                border: `2px solid ${notification.last_available_count > 0 ? '#28a745' : '#dee2e6'}`,
                borderRadius: '4px'
              }}>
                <div style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '4px' }}>
                  Current Availability:
                </div>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: notification.last_available_count > 0 ? '#28a745' : '#6c757d' }}>
                  {notification.last_available_count !== undefined && notification.last_available_count !== null
                    ? `${notification.last_available_count} site${notification.last_available_count !== 1 ? 's' : ''} available`
                    : 'Not checked yet'}
                </div>
                {notification.last_checked && (
                  <div style={{ fontSize: '12px', color: '#6c757d', marginTop: '4px' }}>
                    Last updated: {new Date(notification.last_checked).toLocaleString()}
                  </div>
                )}
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
                  <label htmlFor={`email-${notification.id}`}>Email</label>
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
                  <label htmlFor={`sms-${notification.id}`}>SMS</label>
                </div>
              </div>
              <div className="actions">
                <button
                  className="btn btn-primary"
                  onClick={() => loadAnalytics(notification.facility_id, notification.facility_name)}
                >
                  View Analytics
                </button>
                <button
                  className="btn btn-danger"
                  onClick={() => handleDelete(notification.id)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Analytics Section */}
      {selectedFacility && (
        <div className="card">
          <h3>Availability Analytics: {selectedFacility.name}</h3>
          {loadingAnalytics ? (
            <div className="loading">Loading analytics...</div>
          ) : analyticsData && analyticsData.weekly_stats.length > 0 ? (
            <>
              <p style={{ color: '#666', marginBottom: '20px' }}>
                This chart shows the number of times campsites became available (reserved → available)
                for each week of the year.
              </p>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={analyticsData.weekly_stats}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="week_number"
                    label={{ value: 'Week of Year', position: 'insideBottom', offset: -5 }}
                  />
                  <YAxis
                    label={{ value: 'Availability Changes', angle: -90, position: 'insideLeft' }}
                  />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="availability_changes"
                    stroke="#007bff"
                    name="Times Became Available"
                  />
                </LineChart>
              </ResponsiveContainer>
            </>
          ) : (
            <p style={{ color: '#666' }}>
              No historical data available yet. Analytics will appear after the system has been monitoring
              this campground for a while.
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default Dashboard;
