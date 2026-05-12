import React, { createContext, useContext, useEffect, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const AuthCtx = createContext(null);

export const useAuth = () => useContext(AuthCtx);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem("fs_token"));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    axios
      .get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => setUser(r.data))
      .catch(() => {
        localStorage.removeItem("fs_token");
        setToken(null);
      })
      .finally(() => setLoading(false));
  }, [token]);

  const login = async (email, password) => {
    const r = await axios.post(`${API}/auth/login`, { email, password });
    localStorage.setItem("fs_token", r.data.token);
    setToken(r.data.token);
    setUser(r.data.user);
  };

  const register = async (email, password, name) => {
    const r = await axios.post(`${API}/auth/register`, { email, password, name });
    localStorage.setItem("fs_token", r.data.token);
    setToken(r.data.token);
    setUser(r.data.user);
  };

  const logout = () => {
    localStorage.removeItem("fs_token");
    setToken(null);
    setUser(null);
  };

  const authAxios = axios.create({
    baseURL: API,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  return (
    <AuthCtx.Provider value={{ user, token, loading, login, register, logout, authAxios, API }}>
      {children}
    </AuthCtx.Provider>
  );
};
