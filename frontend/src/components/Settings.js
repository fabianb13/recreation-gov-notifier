import React, { useState, useEffect } from 'react';
import { settingsAPI } from '../api';

const Settings = () => {
  const [scrapeInterval, setScrapeInterval] = useState(300);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await settingsAPI.get();
      setScrapeInterval(response.data.scrape_interval);
    } catch (err) {
      setError('Failed to load settings');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setSaving(true);

    try {
      await settingsAPI.update({ scrape_interval: scrapeInterval });
      setSuccess('Settings saved successfully!');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <div className="container">
      <h2>Settings</h2>

      <div className="card">
        <h3>Polling Configuration</h3>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Check Interval (seconds)</label>
            <input
              type="number"
              value={scrapeInterval}
              onChange={(e) => setScrapeInterval(parseInt(e.target.value))}
              min="60"
              max="3600"
              required
            />
            <small style={{ color: '#666', fontSize: '12px', display: 'block', marginTop: '4px' }}>
              How often to check for campsite availability (60-3600 seconds).
              Current: {Math.floor(scrapeInterval / 60)} minutes
            </small>
          </div>
          {error && <div className="error">{error}</div>}
          {success && <div className="success">{success}</div>}
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </form>
      </div>

      <div className="card">
        <h3>About</h3>
        <p>
          This application monitors Recreation.gov for campsite availability and sends notifications
          when sites become available for your selected dates.
        </p>
        <ul>
          <li>Add campsites by URL or facility ID</li>
          <li>Configure email and SMS notifications</li>
          <li>View historical availability analytics</li>
          <li>Adjust polling frequency to balance timeliness with API usage</li>
        </ul>
      </div>
    </div>
  );
};

export default Settings;
