import React, { useState } from 'react';
import api from './api/axios';
import { Lock, User, Eye, EyeOff, TrendingUp } from 'lucide-react';

const Login = ({ onLoginSuccess }) => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPass, setShowPass] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        
        try {
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);

            const response = await api.post('/token', formData);
            localStorage.setItem('token', response.data.access_token);
            onLoginSuccess();
        } catch (err) {
            setError('Credenciales inválidas. Intenta de nuevo.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
            <div className="w-full max-w-md bg-white rounded-3xl p-8 shadow-2xl">
                <div className="flex flex-col items-center mb-8">
                    <div className="bg-blue-600 p-3 rounded-2xl mb-4 shadow-lg shadow-blue-200">
                        <TrendingUp size={32} className="text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-slate-900">TraderBot v4.0</h1>
                    <p className="text-slate-500 text-sm">Panel de Control Inteligente</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">Usuario</label>
                        <div className="relative">
                            <User className="absolute left-3 top-3.5 text-slate-400" size={18} />
                            <input 
                                type="text"
                                className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                placeholder="Tu usuario"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">Contraseña</label>
                        <div className="relative">
                            <Lock className="absolute left-3 top-3.5 text-slate-400" size={18} />
                            <input 
                                type={showPass ? "text" : "password"}
                                className="w-full pl-10 pr-12 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                            <button 
                                type="button"
                                onClick={() => setShowPass(!showPass)}
                                className="absolute right-3 top-3.5 text-slate-400 hover:text-blue-500"
                            >
                                {showPass ? <EyeOff size={18} /> : <Eye size={18} />}
                            </button>
                        </div>
                    </div>

                    {error && <p className="text-red-500 text-sm text-center font-medium">{error}</p>}

                    <button 
                        type="submit"
                        disabled={loading}
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 rounded-xl shadow-lg shadow-blue-200 transition-all active:scale-95 flex justify-center items-center"
                    >
                        {loading ? "Iniciando sesión..." : "Entrar al Panel"}
                    </button>
                </form>
            </div>
        </div>
    );
};

export default Login;