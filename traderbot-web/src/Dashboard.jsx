import React, { useEffect, useState, useCallback } from 'react';
import api from './api/axios';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp, TrendingDown, DollarSign, PieChart, Activity, LogOut, RefreshCw, Clock } from 'lucide-react';

const Dashboard = ({ onLogout }) => {
    const [summary, setSummary] = useState(null);
    const [history, setHistory] = useState([]);
    const [trades, setTrades] = useState([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [lastUpdate, setLastUpdate] = useState(new Date());
    const [autoRefreshSeconds, setAutoRefreshSeconds] = useState(30);

    // Función de carga de datos optimizada
    const fetchData = useCallback(async (isManual = false) => {
        if (isManual) setRefreshing(true);
        try {
            const [s, h, t] = await Promise.all([
                api.get('/stats/summary'),
                api.get('/stats/history'),
                api.get('/stats/trades')
            ]);
            setSummary(s.data);
            setHistory(h.data);
            setTrades(t.data);
            setLastUpdate(new Date());
        } catch (err) {
            console.error("Error cargando datos", err);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, []);

    // Efecto para Refresco Automático
    useEffect(() => {
        fetchData(); // Carga inicial
        
        const interval = setInterval(() => {
            fetchData();
        }, autoRefreshSeconds * 1000);

        return () => clearInterval(interval);
    }, [fetchData, autoRefreshSeconds]);

    if (loading) {
        return (
            <div className="flex h-screen w-full items-center justify-center bg-slate-950">
                <div className="flex flex-col items-center gap-4">
                    <div className="h-12 w-12 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"></div>
                    <p className="text-slate-400 font-medium animate-pulse">Sincronizando con MT5...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 text-slate-900 overflow-x-hidden">
            {/* Header / Navbar Profesional */}
            <nav className="bg-white/80 backdrop-blur-md border-b px-4 py-3 sticky top-0 z-50 flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <div className="bg-blue-600 p-2 rounded-xl text-white shadow-lg shadow-blue-200">
                        <Activity size={20}/>
                    </div>
                    <div>
                        <h1 className="font-bold text-base leading-tight">TraderBot <span className="text-blue-600">v4.0</span></h1>
                        <div className="flex items-center gap-1 text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                            <Clock size={10}/> Actualizado: {lastUpdate.toLocaleTimeString()}
                        </div>
                    </div>
                </div>
                
                <div className="flex items-center gap-3">
                    {/* Botón Refresco Manual */}
                    <button 
                        onClick={() => fetchData(true)}
                        className={`p-2 rounded-xl border transition-all active:scale-90 ${refreshing ? 'bg-blue-50 text-blue-600' : 'bg-white text-slate-500'}`}
                    >
                        <RefreshCw size={20} className={refreshing ? "animate-spin" : ""} />
                    </button>
                    <button onClick={onLogout} className="p-2 rounded-xl border bg-white text-slate-400 hover:text-red-500 transition-colors">
                        <LogOut size={20}/>
                    </button>
                </div>
            </nav>

            <main className="max-w-7xl mx-auto px-4 mt-6 space-y-6 animate-in fade-in duration-700">
                
                {/* Selector de Auto-refresco (Mobile friendly) */}
                <div className="flex items-center justify-between bg-white p-3 rounded-2xl border shadow-sm">
                    <span className="text-xs font-bold text-slate-500 uppercase px-2">Auto-Refresco</span>
                    <select 
                        value={autoRefreshSeconds} 
                        onChange={(e) => setAutoRefreshSeconds(Number(e.target.value))}
                        className="bg-slate-100 text-xs font-bold py-1 px-3 rounded-lg outline-none border-none focus:ring-2 focus:ring-blue-500"
                    >
                        <option value={15}>15s</option>
                        <option value={30}>30s</option>
                        <option value={60}>1m</option>
                        <option value={300}>5m</option>
                    </select>
                </div>

                {/* Status Bot */}
                <div className={`p-4 rounded-2xl border flex items-center justify-between shadow-sm ${summary.is_active ? 'bg-emerald-50/50 border-emerald-100' : 'bg-red-50/50 border-red-100'}`}>
                    <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${summary.is_active ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`}></div>
                        <span className="font-bold text-sm text-slate-700">{summary.is_active ? 'SISTEMA ONLINE' : 'SISTEMA OFFLINE'}</span>
                    </div>
                    <span className="text-[10px] font-black text-slate-400 tracking-tighter uppercase">Real-Time Data</span>
                </div>

                {/* KPI Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard title="Balance" value={`$${summary.current_balance.toLocaleString()}`} icon={<DollarSign size={18}/>} color="blue" />
                    <StatCard title="Total Profit" value={`$${summary.total_profit.toLocaleString()}`} icon={<TrendingUp size={18}/>} color="emerald" />
                    <StatCard title="Win Rate" value={`${summary.win_rate}%`} icon={<PieChart size={18}/>} color="indigo" />
                    <StatCard title="Trades" value={summary.total_trades} icon={<Activity size={18}/>} color="orange" />
                </div>

                {/* Gráfica Equity */}
                <div className="bg-white p-6 rounded-3xl border shadow-sm">
                    <h3 className="text-slate-800 font-bold mb-6 flex items-center gap-2 text-sm">
                        <TrendingUp size={18} className="text-blue-600"/> RENDIMIENTO HISTÓRICO
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
                                    contentStyle={{ borderRadius: '20px', border: 'none', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)' }}
                                    formatter={(value) => [`$${value.toLocaleString()}`, 'Balance']}
                                />
                                <Area type="monotone" dataKey="balance" stroke="#3b82f6" strokeWidth={4} fillOpacity={1} fill="url(#colorBalance)" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Lista de Trades */}
                <div className="bg-white rounded-3xl border shadow-sm overflow-hidden mb-8">
                    <div className="p-5 border-b flex justify-between items-center bg-slate-50/50">
                        <h3 className="font-bold text-slate-800 text-sm italic">Live Journal</h3>
                        <div className="text-[10px] font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded-full">Últimos 10</div>
                    </div>
                    <div className="divide-y divide-slate-100">
                        {trades.length > 0 ? trades.map(trade => (
                            <div key={trade.id} className="p-4 flex items-center justify-between active:bg-slate-50 transition-colors">
                                <div className="flex items-center gap-3">
                                    <div className={`p-2.5 rounded-xl ${trade.profit > 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-600'}`}>
                                        {trade.profit > 0 ? <TrendingUp size={16}/> : <TrendingDown size={16}/>}
                                    </div>
                                    <div>
                                        <div className="font-bold text-slate-800 text-sm">{trade.symbol}</div>
                                        <div className="text-[10px] text-slate-400 font-bold uppercase">{trade.type} • {trade.close_time}</div>
                                    </div>
                                </div>
                                <div className={`font-black text-sm ${trade.profit > 0 ? 'text-emerald-500' : 'text-red-500'}`}>
                                    {trade.profit > 0 ? '+' : ''}{trade.profit.toFixed(2)}
                                </div>
                            </div>
                        )) : (
                            <div className="p-10 text-center text-slate-400 text-sm">No hay operaciones recientes</div>
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
};

const StatCard = ({ title, value, icon, color }) => {
    const colors = {
        blue: "bg-blue-600 text-white shadow-blue-100",
        emerald: "bg-emerald-500 text-white shadow-emerald-100",
        indigo: "bg-indigo-600 text-white shadow-indigo-100",
        orange: "bg-orange-500 text-white shadow-orange-100"
    };
    return (
        <div className="bg-white p-4 rounded-[2rem] border border-slate-100 shadow-sm flex flex-col items-center text-center">
            <div className={`w-10 h-10 rounded-2xl flex items-center justify-center mb-2 shadow-lg ${colors[color]}`}>
                {icon}
            </div>
            <div className="text-slate-400 text-[9px] font-black uppercase tracking-tighter mb-1">{title}</div>
            <div className="text-base font-black text-slate-900 truncate w-full">{value}</div>
        </div>
    );
};

export default Dashboard;