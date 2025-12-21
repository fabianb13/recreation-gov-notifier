import axios from 'axios';

// Use the current host for API calls to support mobile devices
// Falls back to localhost for local development
const getApiUrl = () => {
  if (process.env.REACT_APP_API_URL && process.env.REACT_APP_API_URL !== 'http://localhost:8000') {
    return process.env.REACT_APP_API_URL;
  }
  
  // Use the current host's protocol and hostname with port 8000
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    return `${protocol}//${hostname}:8000`;
  }
  
  return 'http://localhost:8000';
};

const API_URL = getApiUrl();

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Handle 401 responses
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  register: (email, password, phoneNumber) =>
    api.post('/api/auth/register', { email, password, phone_number: phoneNumber }),
  login: (email, password) =>
    api.post('/api/auth/login', { email, password }),
  getMe: () =>
    api.get('/api/auth/me'),
};

// Notifications API
export const notificationsAPI = {
  getAll: () =>
    api.get('/api/notifications'),
  create: (data) =>
    api.post('/api/notifications', data),
  update: (id, data) =>
    api.put(`/api/notifications/${id}`, data),
  delete: (id) =>
    api.delete(`/api/notifications/${id}`),
};

// Settings API
export const settingsAPI = {
  get: () =>
    api.get('/api/settings'),
  update: (data) =>
    api.put('/api/settings', data),
};

// Analytics API
export const analyticsAPI = {
  getFacilityAnalytics: (facilityId) =>
    api.get(`/api/analytics/${facilityId}`),
};

export default api;
