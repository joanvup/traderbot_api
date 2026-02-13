import React, { useState, useEffect } from 'react';
import Login from './Login';
import Dashboard from './Dashboard';

function App() {
  const [isLogged, setIsLogged] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) setIsLogged(true);
  }, []);

  const logout = () => {
    localStorage.removeItem('token');
    setIsLogged(false);
  };

  if (!isLogged) {
    return <Login onLoginSuccess={() => setIsLogged(true)} />;
  }

  return <Dashboard onLogout={logout} />;
}

export default App;