import axios from 'axios';

const api = axios.create({
    // Localmente usa la IP de tu PC o localhost. En producción cambiar a tu URL https
    baseURL: 'http://localhost:8000', 
});

// Interceptor para incluir el token JWT en cada petición automáticamente
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export default api;