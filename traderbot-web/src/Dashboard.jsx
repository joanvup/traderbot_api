import React, { useEffect, useState, useCallback } from 'react';
import api from './api/axios';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp, TrendingDown, DollarSign, Activity, LogOut, RefreshCw, Clock, Cpu, Zap, ShieldCheck, FileText, Table as TableIcon, ChevronLeft, ChevronRight } from 'lucide-react';
import jsPDF from 'jspdf';
import 'jspdf-autotable';

const Dashboard = ({ onLogout }) => {
    const [summary, setSummary] = useState(null);
    const [history, setHistory] = useState([]);
    const [trades, setTrades] = useState([]);
    const [monitoring, setMonitoring] = useState([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [lastUpdate, setLastUpdate] = useState(new Date());
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const tradesPerPage = 10;

    const fetchData = useCallback(async (isManual = false) => {
        if (isManual) setRefreshing(true);
        try {
            const [s, h, t, m] = await Promise.all([
                api.get('/stats/summary'),
                api.get('/stats/history'),
                api.get(`/stats/trades?page=${currentPage}&limit=${tradesPerPage}`),
                api.get('/stats/monitoring')
            ]);
            setSummary(s.data); setHistory(h.data); 
            setTrades(t.data.trades); 
            setTotalPages(Math.ceil(t.data.total_trades / tradesPerPage));
            setMonitoring(m.data);
            setLastUpdate(new Date());
        } catch (err) { console.error("Error cargando datos", err); } 
        finally { setLoading(false); setRefreshing(false); }
    }, [currentPage]); // Dependencia currentPage para recargar al cambiar de página

    useEffect(() => {
        fetchData();
        const interval = setInterval(() => fetchData(), 15000);
        return () => clearInterval(interval);
    }, [fetchData]);

    const handlePageChange = (newPage) => {
        if (newPage > 0 && newPage <= totalPages) {
            setCurrentPage(newPage);
        }
    };

    // Funciones de Exportación (Mantener las que ya tenías)
    const exportPDF = () => { /* ... (código existente) ... */ };
    const exportCSV = async () => { /* ... (código existente) ... */ };

    if (loading) return <LoadingScreen />;

    return (
        <div className="min-h-screen bg-[#0a0f1c] text-slate-100 font-sans selection:bg-blue-500/30">
            {/* Header Pro */}
            <nav className="bg-[#0f172a]/80 backdrop-blur-xl border-b border-white/5 px-6 py-4 sticky top-0 z-50 flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <div className="bg-gradient-to-br from-blue-500 to-indigo-600 p-2.5 rounded-2xl shadow-lg shadow-blue-500/20">
                        <Cpu size={22} className="text-white animate-pulse"/>
                    </div>
                    <div>
                        <h1 className="font-black text-lg tracking-tight uppercase italic text-transparent bg-clip-text bg-gradient-to-r from-white to-slate-400">AI Sentinel <span className="text-blue-500">v6.0</span></h1>
                        <div className="flex items-center gap-1.5 text-[10px] text-slate-500 font-bold uppercase tracking-widest">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></div>
                            Live Feed: {lastUpdate.toLocaleTimeString()}
                        </div>
                    </div>
                </div>
                <div className="flex gap-3">
                    <button onClick={() => fetchData(true)} className={`p-2.5 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-all ${refreshing ? 'text-blue-400' : 'text-slate-400'}`}>
                        <RefreshCw size={20} className={refreshing ? "animate-spin" : ""} />
                    </button>
                    <button onClick={onLogout} className="p-2.5 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500 hover:text-white transition-all">
                        <LogOut size={20}/>
                    </button>
                </div>
            </nav>

            <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">
                
                {/* Métricas Principales */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <KPI icon={<DollarSign/>} label="Balance" val={`$${summary.current_balance.toLocaleString()}`} color="blue" />
                    <KPI icon={<TrendingUp/>} label="Net Profit" val={`$${summary.total_profit.toLocaleString()}`} color="emerald" />
                    <KPI icon={<Zap/>} label="Win Rate" val={`${summary.win_rate}%`} color="violet" />
                    <KPI icon={<Activity/>} label="Trades" val={summary.total_trades} color="amber" />
                </div>

                {/* SECCIÓN DE VIGILANCIA IA */}
                <section>
                    <div className="flex items-center gap-2 mb-4 px-1">
                        <ShieldCheck className="text-blue-500" size={20}/>
                        <h2 className="text-sm font-black uppercase tracking-[0.2em] text-slate-400">AI Market Surveillance</h2>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {monitoring.map(m => (
                            <MarketCard key={m.symbol} data={m} />
                        ))}
                    </div>
                </section>

                {/* Gráfica de Rendimiento */}
                <div className="bg-[#0f172a] border border-white/5 p-6 rounded-[2.5rem] shadow-2xl">
                    <div className="flex justify-between items-center mb-8">
                        <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">Equity Growth Curve</h3>
                        <div className="text-blue-500 bg-blue-500/10 px-3 py-1 rounded-full text-[10px] font-bold">H1 Timeframe</div>
                    </div>
                    <div className="h-72 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={history}>
                                <defs>
                                    <linearGradient id="glow" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.4}/>
                                        <stop offset="100%" stopColor="#3b82f6" stopOpacity={0}/>
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="0" vertical={false} stroke="rgba(255,255,255,0.03)" />
                                <XAxis dataKey="time" hide />
                                <YAxis domain={['auto', 'auto']} hide />
                                <Tooltip content={<CustomTooltip />} />
                                <Area type="monotone" dataKey="balance" stroke="#3b82f6" strokeWidth={4} fill="url(#glow)" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Diario de Operaciones con Paginación */}
                <div className="bg-[#0f172a] border border-white/5 rounded-[2.5rem] overflow-hidden">
                    <div className="p-6 border-b border-white/5 flex justify-between items-center bg-white/[0.02]">
                        <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">Live Execution Log</h3>
                        <div className="flex gap-2">
                            <button onClick={exportCSV} className="p-2 rounded-xl bg-white/5 text-slate-400 hover:text-white transition-all">
                                <TableIcon size={18}/>
                            </button>
                            <button onClick={exportPDF} className="p-2 rounded-xl bg-white/5 text-slate-400 hover:text-white transition-all">
                                <FileText size={18}/>
                            </button>
                        </div>
                    </div>
                    <div className="divide-y divide-white/5">
                        {trades.length > 0 ? trades.map(t => (
                            <div key={t.id} className="p-5 flex items-center justify-between hover:bg-white/[0.02] transition-all">
                                <div className="flex items-center gap-4">
                                    <div className={`p-3 rounded-2xl ${t.profit > 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                                        {t.profit > 0 ? <TrendingUp size={16}/> : <TrendingDown size={16}/>}
                                    </div>
                                    <div>
                                        <div className="font-black text-sm">{t.symbol}</div>
                                        <div className="text-[10px] font-bold text-slate-500 uppercase">
                                            {t.type} • Open: {t.open_time.split(' ')[1]} • Close: {t.close_time.split(' ')[1]}
                                        </div>
                                    </div>
                                </div>
                                <div className={`font-mono font-bold ${t.profit > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                    {t.profit > 0 ? '+' : ''}{t.profit.toFixed(2)}
                                </div>
                            </div>
                        )) : (
                            <div className="p-10 text-center text-slate-500 text-sm">No hay operaciones recientes</div>
                        )}
                    </div>
                    {/* Controles de Paginación */}
                    {totalPages > 1 && (
                        <div className="p-4 border-t border-white/5 flex justify-center items-center gap-4 bg-white/[0.02]">
                            <button 
                                onClick={() => handlePageChange(currentPage - 1)} 
                                disabled={currentPage === 1}
                                className="p-2 rounded-lg bg-white/5 text-slate-400 hover:text-blue-400 disabled:opacity-50"
                            >
                                <ChevronLeft size={20}/>
                            </button>
                            <span className="text-sm font-bold text-slate-300">Página {currentPage} de {totalPages}</span>
                            <button 
                                onClick={() => handlePageChange(currentPage + 1)} 
                                disabled={currentPage === totalPages}
                                className="p-2 rounded-lg bg-white/5 text-slate-400 hover:text-blue-400 disabled:opacity-50"
                            >
                                <ChevronRight size={20}/>
                            </button>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
};

// --- SUBCOMPONENTES (mantienen su lógica) ---
const MarketCard = ({ data }) => { /* ... (código existente) ... */ };
const KPI = ({ icon, label, val, color }) => { /* ... (código existente) ... */ };
const CustomTooltip = ({ active, payload }) => { /* ... (código existente) ... */ };
const LoadingScreen = () => ( /* ... (código existente) ... */ );

export default Dashboard;