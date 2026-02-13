import React, { useEffect, useState } from 'react';
import api from './api/axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { TrendingUp, TrendingDown, DollarSign, PieChart, Activity, LogOut, Menu } from 'lucide-react';

const Dashboard = ({ onLogout }) => {
    const [summary, setSummary] = useState(null);
    const [history, setHistory] = useState([]);
    const [trades, setTrades] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            const [s, h, t] = await Promise.all([
                api.get('/stats/summary'),
                api.get('/stats/history'),
                api.get('/stats/trades')
            ]);
            setSummary(s.data);
            setHistory(h.data);
            setTrades(t.data);
        } catch (err) {
            console.error("Error cargando datos", err);
        } finally {
            setLoading(false);
        }
    };

    if (loading) return <div className="flex h-screen items-center justify-center">Cargando datos...</div>;

    return (
        <div className="min-h-screen bg-slate-50 pb-10">
            {/* Header / Navbar Móvil */}
            <nav className="bg-white border-b px-4 py-4 sticky top-0 z-10 flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <div className="bg-blue-600 p-2 rounded-lg text-white"><Activity size={20}/></div>
                    <span className="font-bold text-lg tracking-tight">TraderBot <span className="text-blue-600">v4.0</span></span>
                </div>
                <button onClick={onLogout} className="text-slate-400 hover:text-red-500 transition-colors"><LogOut size={22}/></button>
            </nav>

            <main className="max-w-7xl mx-auto px-4 mt-6 space-y-6">
                
                {/* Status Card - Solo Móvil/Tablet */}
                <div className={`p-4 rounded-2xl border flex items-center justify-between ${summary.is_active ? 'bg-emerald-50 border-emerald-100' : 'bg-red-50 border-red-100'}`}>
                    <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full animate-pulse ${summary.is_active ? 'bg-emerald-500' : 'bg-red-500'}`}></div>
                        <span className="font-semibold text-slate-700">{summary.is_active ? 'Bot En Ejecución' : 'Bot Detenido'}</span>
                    </div>
                    <span className="text-xs font-bold uppercase text-slate-400 tracking-widest">Live System</span>
                </div>

                {/* KPI Cards Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard title="Balance" value={`$${summary.current_balance}`} icon={<DollarSign size={20}/>} color="blue" />
                    <StatCard title="Total Profit" value={`$${summary.total_profit}`} icon={<TrendingUp size={20}/>} color="emerald" />
                    <StatCard title="Win Rate" value={`${summary.win_rate}%`} icon={<PieChart size={20}/>} color="indigo" />
                    <StatCard title="Trades" value={summary.total_trades} icon={<Activity size={20}/>} color="orange" />
                </div>

                {/* Gráfica de Rendimiento Profesional */}
                <div className="bg-white p-6 rounded-3xl border shadow-sm">
                    <h3 className="text-slate-800 font-bold mb-6 flex items-center gap-2">
                        <TrendingUp size={20} className="text-blue-600"/> Curva de Equidad
                    </h3>
                    <div className="h-64 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={history}>
                                <defs>
                                    <linearGradient id="colorBalance" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                <XAxis dataKey="time" hide />
                                <YAxis domain={['auto', 'auto']} hide />
                                <Tooltip 
                                    contentStyle={{ borderRadius: '16px', border: 'none', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }}
                                    formatter={(value) => [`$${value}`, 'Balance']}
                                />
                                <Area type="monotone" dataKey="balance" stroke="#3b82f6" strokeWidth={3} fillOpacity={1} fill="url(#colorBalance)" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Últimos Trades - Lista Responsiva */}
                <div className="bg-white rounded-3xl border shadow-sm overflow-hidden">
                    <div className="p-6 border-b flex justify-between items-center">
                        <h3 className="font-bold text-slate-800">Últimas Operaciones</h3>
                        <button className="text-blue-600 text-sm font-semibold">Ver Todo</button>
                    </div>
                    <div className="divide-y">
                        {trades.map(trade => (
                            <div key={trade.id} className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
                                <div className="flex items-center gap-3">
                                    <div className={`p-2 rounded-xl ${trade.profit > 0 ? 'bg-emerald-100 text-emerald-600' : 'bg-red-100 text-red-600'}`}>
                                        {trade.profit > 0 ? <TrendingUp size={18}/> : <TrendingDown size={18}/>}
                                    </div>
                                    <div>
                                        <div className="font-bold text-slate-800">{trade.symbol}</div>
                                        <div className="text-xs text-slate-400 font-medium uppercase">{trade.type} • {trade.close_time}</div>
                                    </div>
                                </div>
                                <div className={`font-bold text-sm ${trade.profit > 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                                    {trade.profit > 0 ? '+' : ''}{trade.profit.toFixed(2)}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </main>
        </div>
    );
};

const StatCard = ({ title, value, icon, color }) => {
    const colors = {
        blue: "bg-blue-50 text-blue-600",
        emerald: "bg-emerald-50 text-emerald-600",
        indigo: "bg-indigo-50 text-indigo-600",
        orange: "bg-orange-50 text-orange-600"
    };
    return (
        <div className="bg-white p-4 rounded-3xl border shadow-sm">
            <div className={`w-10 h-10 rounded-2xl flex items-center justify-center mb-3 ${colors[color]}`}>
                {icon}
            </div>
            <div className="text-slate-400 text-xs font-medium uppercase tracking-wider">{title}</div>
            <div className="text-xl font-bold text-slate-900 mt-1 truncate">{value}</div>
        </div>
    );
};

export default Dashboard;