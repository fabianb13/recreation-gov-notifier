import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';

const Navbar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="navbar">
      <div className="container">
        <h1>🏕️ Recreation.gov Notifier</h1>
        {user && (
          <nav>
            <Link to="/dashboard">Dashboard</Link>
            <Link to="/settings">Settings</Link>
            <button
              onClick={handleLogout}
              className="btn btn-secondary"
              style={{ padding: '6px 12px', fontSize: '14px' }}
            >
              Logout
            </button>
          </nav>
        )}
      </div>
    </div>
  );
};

export default Navbar;
