import React, { useEffect, useState, useCallback } from 'react';
import api from './api/axios';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import {
    TrendingUp, TrendingDown, DollarSign, Activity, LogOut, RefreshCw,
    Clock, Cpu, Zap, ShieldCheck, FileText, Table as TableIcon,
    ChevronLeft, ChevronRight, Target, Navigation
} from 'lucide-react';
import jsPDF from 'jspdf';
import 'jspdf-autotable';

const Dashboard = ({ onLogout }) => {
    const [summary, setSummary] = useState(null);
    const [history, setHistory] = useState([]);
    const [trades, setTrades] = useState([]);
    const [monitoring, setMonitoring] = useState([]);
    const [activeTrades, setActiveTrades] = useState([]);

    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [lastUpdate, setLastUpdate] = useState(new Date());
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const tradesPerPage = 10;

    const fetchData = useCallback(async (isManual = false) => {
        if (isManual) setRefreshing(true);
        try {
            const [resSum, resHis, resTra, resMon, resActive] = await Promise.all([
                api.get('/stats/summary'),
                api.get('/stats/history'),
                api.get(`/stats/trades?page=${currentPage}&limit=${tradesPerPage}`),
                api.get('/stats/monitoring'),
                api.get('/stats/active-trades')
            ]);

            setSummary(resSum.data);
            setHistory(resHis.data);
            setTrades(resTra.data.trades);
            setTotalPages(Math.ceil(resTra.data.total_trades / tradesPerPage));
            setMonitoring(resMon.data);
            setActiveTrades(resActive.data);
            setLastUpdate(new Date());
        } catch (err) {
            console.error("Error en la sincronización de datos:", err);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [currentPage]);

    useEffect(() => {
        fetchData();
        const interval = setInterval(() => fetchData(), 15000);
        return () => clearInterval(interval);
    }, [fetchData]);

    const handlePrevPage = () => { if (currentPage > 1) setCurrentPage(currentPage - 1); };
    const handleNextPage = () => { if (currentPage < totalPages) setCurrentPage(currentPage + 1); };

    const exportPDF = () => {
        const doc = new jsPDF();
        doc.text("SENTINEL AI - REPORTE", 14, 20);
        doc.autoTable({
            head: [['Activo', 'Tipo', 'Profit', 'Cierre']],
            body: trades.map(t => [t.symbol, t.type, t.profit.toFixed(2), t.close_time]),
            startY: 30
        });
        doc.save(`Reporte_${new Date().getTime()}.pdf`);
    };

    const exportCSV = async () => {
        try {
            const response = await api.get('/export/csv', { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'traderbot_history.csv');
            link.click();
        } catch (err) { alert("Error CSV"); }
    };

    if (loading) return <LoadingScreen />;

    return (
        <div className="min-h-screen bg-[#0a0f1c] text-slate-100 font-sans pb-20">
            <nav className="bg-[#0f172a]/80 backdrop-blur-xl border-b border-white/5 px-6 py-4 sticky top-0 z-50 flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <div className="bg-gradient-to-br from-blue-500 to-indigo-600 p-2.5 rounded-2xl shadow-lg shadow-blue-500/20">
                        <Cpu size={22} className="text-white animate-pulse" />
                    </div>
                    <div>
                        <h1 className="font-black text-lg tracking-tight uppercase italic text-transparent bg-clip-text bg-gradient-to-r from-white to-slate-400">
                            AI Sentinel <span className="text-blue-500">v6.1</span>
                        </h1>
                        <div className="flex items-center gap-1.5 text-[10px] text-slate-500 font-bold uppercase tracking-widest">
                            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></div>
                            Actualizado: {lastUpdate.toLocaleTimeString()}
                        </div>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button onClick={() => fetchData(true)} className={`p-2.5 rounded-xl bg-white/5 border border-white/10 transition-all ${refreshing ? 'text-blue-400' : 'text-slate-400'}`}>
                        <RefreshCw size={20} className={refreshing ? "animate-spin" : ""} />
                    </button>
                    <button onClick={onLogout} className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500 hover:text-white transition-all">
                        <LogOut size={20} />
                    </button>
                </div>
            </nav>

            <main className="max-w-7xl mx-auto px-4 py-8 space-y-10">
                {/* KPI CARDS */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <KPI icon={<DollarSign />} label="Balance Real" val={`$${summary?.current_balance?.toLocaleString() || '0.00'}`} color="blue" />
                    <KPI icon={<TrendingUp />} label="Net Profit" val={`$${summary?.total_profit?.toLocaleString() || '0.00'}`} color="emerald" />
                    <KPI icon={<Zap />} label="Win Rate" val={`${summary?.win_rate}%`} color="violet" />
                    <KPI icon={<Activity />} label="Open Positions" val={activeTrades.length} color="amber" />
                </div>

                {/* AI SURVEILLANCE UNIT (CORREGIDO) */}
                <section>
                    <div className="flex items-center gap-2 mb-6 px-1">
                        <ShieldCheck className="text-blue-500" size={20} />
                        <h2 className="text-sm font-black uppercase tracking-widest text-slate-400">AI Surveillance Unit</h2>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {monitoring.map(m => {
                            // Sincronización lógica: Buscamos si el activo está realmente abierto en MT5
                            const liveData = activeTrades.find(t => t.symbol === m.symbol);
                            return (
                                <MarketCard
                                    key={m.symbol}
                                    data={m}
                                    liveData={liveData}
                                />
                            );
                        })}
                    </div>
                </section>

                {/* EQUITY GRAPH */}
                <div className="bg-[#0f172a] border border-white/5 p-6 rounded-[2.5rem] shadow-2xl">
                    <div className="flex justify-between items-center mb-8">
                        <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">Equity Performance History</h3>
                        <div className="text-blue-500 bg-blue-500/10 px-3 py-1 rounded-full text-[10px] font-bold uppercase">Live Account</div>
                    </div>
                    <div className="h-72 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={history}>
                                <defs>
                                    <linearGradient id="glow" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.4} />
                                        <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
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

                {/* HISTORIAL LOG */}
                <div className="bg-[#0f172a] border border-white/5 rounded-[2.5rem] overflow-hidden shadow-2xl">
                    <div className="p-6 border-b border-white/5 flex justify-between items-center bg-white/[0.02]">
                        <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">Live Execution Log</h3>
                        <div className="flex gap-2">
                            <button onClick={exportCSV} className="p-2 rounded-xl bg-white/5 text-slate-400 hover:text-white border border-white/5"><TableIcon size={18} /></button>
                            <button onClick={exportPDF} className="p-2 rounded-xl bg-white/5 text-slate-400 hover:text-white border border-white/5"><FileText size={18} /></button>
                        </div>
                    </div>
                    <div className="divide-y divide-white/5">
                        {trades.length > 0 ? trades.map(t => (
                            <div key={t.id} className="p-5 flex items-center justify-between hover:bg-white/[0.02] transition-all">
                                <div className="flex items-center gap-4">
                                    <div className={`p-3 rounded-2xl ${t.profit > 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                                        {t.profit > 0 ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                                    </div>
                                    <div>
                                        <div className="font-black text-sm">{t.symbol} <span className="ml-2 text-[10px] text-slate-500">#{t.ticket}</span></div>
                                        <div className="text-[10px] font-bold text-slate-400 uppercase leading-relaxed">
                                            <span className={t.type === 'BUY' ? 'text-blue-400' : 'text-orange-400'}>{t.type}</span> •
                                            <span className="text-slate-500 ml-1">IN: {t.open_time}</span> •
                                            <span className="text-slate-500 ml-1">OUT: {t.close_time}</span>
                                        </div>
                                    </div>
                                </div>
                                <div className="text-right font-mono font-black">
                                    <div className={t.profit > 0 ? 'text-emerald-400' : 'text-red-400'}>{t.profit > 0 ? '+' : ''}{t.profit.toFixed(2)}</div>
                                </div>
                            </div>
                        )) : <div className="p-20 text-center text-slate-600 font-bold uppercase text-xs">No records</div>}
                    </div>
                    {totalPages > 1 && (
                        <div className="p-4 border-t border-white/5 flex justify-center gap-6 bg-white/[0.01]">
                            <button onClick={handlePrevPage} disabled={currentPage === 1} className="p-2 rounded-xl bg-white/5 text-slate-400 disabled:opacity-20"><ChevronLeft size={24} /></button>
                            <span className="text-xs font-black text-slate-500 uppercase flex items-center">Pág {currentPage} / {totalPages}</span>
                            <button onClick={handleNextPage} disabled={currentPage === totalPages} className="p-2 rounded-xl bg-white/5 text-slate-400 disabled:opacity-20"><ChevronRight size={24} /></button>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
};

// --- COMPONENTES AUXILIARES ---

const MarketCard = ({ data, liveData }) => {
    // Regla de Integridad
    const isTradeActive = !!liveData;

    let currentStatus = data.status;
    if (data.status === 'ABIERTA' && !isTradeActive) {
        currentStatus = 'ESPERAR';
    } else if (isTradeActive) {
        currentStatus = 'ABIERTA';
    }

    const isBullish = isTradeActive ? (liveData.type === 'BUY') : (data.ia_prob > 0.5);

    return (
        <div className={`bg-[#0f172a] border ${isTradeActive ? 'border-blue-500/50 shadow-blue-500/10 shadow-lg' : 'border-white/5'} p-6 rounded-[2rem] relative overflow-hidden transition-all group`}>
            {/* Efecto de resplandor dinámico */}
            {isTradeActive && (
                <div className={`absolute -top-10 -right-10 w-32 h-32 blur-[60px] opacity-20 ${liveData.type === 'BUY' ? 'bg-blue-600' : 'bg-orange-600'}`}></div>
            )}

            <div className="flex justify-between items-start mb-6">
                <div>
                    <h4 className="font-black text-xl tracking-tight text-white flex items-center gap-2">
                        {data.symbol}
                        {isTradeActive && <div className="w-2 h-2 rounded-full bg-emerald-500 animate-ping"></div>}
                    </h4>

                    {/* INDICADOR DE TIPO (COMPRA O VENTA) - Solo si está activa */}
                    {isTradeActive ? (
                        <div className={`mt-1.5 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg text-[10px] font-black uppercase tracking-widest ${liveData.type === 'BUY' ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/50' : 'bg-orange-600 text-white shadow-lg shadow-orange-900/50'}`}>
                            {liveData.type === 'BUY' ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                            {liveData.type === 'BUY' ? 'Long / Compra' : 'Short / Venta'}
                        </div>
                    ) : (
                        <p className="text-[11px] font-mono text-slate-500 mt-0.5">
                            ${data.price.toFixed(5)}
                        </p>
                    )}
                </div>
                <div className={`px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-tighter ${isTradeActive ? 'bg-white/10 text-white' : 'bg-white/5 text-slate-600'}`}>
                    {currentStatus}
                </div>
            </div>

            {isTradeActive ? (
                /* VISTA TERMINAL (OPERACIÓN VIVA) */
                <div className="space-y-4 animate-in fade-in zoom-in duration-500">
                    <div className="grid grid-cols-2 gap-3">
                        <div className="bg-white/[0.03] p-3 rounded-2xl border border-white/5">
                            <p className="text-[8px] font-black text-slate-500 uppercase mb-1">Entry Price</p>
                            <p className="font-mono text-xs font-bold text-slate-200">{liveData.price_open.toFixed(5)}</p>
                        </div>
                        <div className="bg-blue-500/[0.03] p-3 rounded-2xl border border-blue-500/10">
                            <p className="text-[8px] font-black text-blue-500 uppercase mb-1">Current</p>
                            <p className="font-mono text-xs font-bold text-blue-400 animate-pulse">{liveData.price_current.toFixed(5)}</p>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        <div className="bg-red-500/[0.03] p-3 rounded-2xl border border-red-500/10">
                            <p className="text-[8px] font-black text-red-600 uppercase mb-1 flex items-center gap-1"><Target size={10} /> Stop Loss</p>
                            <p className="font-mono text-xs font-bold text-red-400">{liveData.sl.toFixed(5)}</p>
                        </div>
                        <div className="bg-emerald-500/[0.03] p-3 rounded-2xl border border-emerald-500/10">
                            <p className="text-[8px] font-black text-emerald-600 uppercase mb-1 flex items-center gap-1"><Navigation size={10} /> Take Profit</p>
                            <p className="font-mono text-xs font-bold text-emerald-400">{liveData.tp.toFixed(5)}</p>
                        </div>
                    </div>
                    <div className="pt-2 flex justify-between items-center border-t border-white/5">
                        <span className="text-[10px] font-black text-slate-500 uppercase tracking-tighter">Live Position Profit</span>
                        <span className={`text-xl font-black font-mono ${liveData.profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {liveData.profit >= 0 ? '+' : ''}{liveData.profit.toFixed(2)} <span className="text-[10px] text-slate-600">USD</span>
                        </span>
                    </div>
                </div>
            ) : (
                /* VISTA IA (ESCANEANDO) */
                <div className="space-y-4">
                    <div className="flex justify-between items-end">
                        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">AI Reliability</span>
                        <span className={`text-lg font-mono font-black ${data.ia_prob > 0.5 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {(data.ia_prob * 100).toFixed(1)}%
                        </span>
                    </div>
                    <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                        <div
                            className={`h-full transition-all duration-1000 ${data.ia_prob > 0.5 ? 'bg-emerald-500' : 'bg-red-500'}`}
                            style={{ width: `${data.ia_prob * 100}%` }}
                        ></div>
                    </div>
                    <div className="flex justify-between text-[10px] font-bold text-slate-600 uppercase">
                        <span>RSI: {data.rsi.toFixed(1)}</span>
                        <span>{data.ia_prob > 0.5 ? 'Bullish Bias' : 'Bearish Bias'}</span>
                    </div>
                </div>
            )}
        </div>
    );
};

const KPI = ({ icon, label, val, color }) => {
    const colors = { blue: "text-blue-400", emerald: "text-emerald-400", violet: "text-violet-400", amber: "text-amber-400" };
    return (
        <div className="bg-[#0f172a] border border-white/5 p-5 rounded-[2rem] flex flex-col items-center text-center shadow-xl">
            <div className={`mb-2 ${colors[color]}`}>{icon}</div>
            <span className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">{label}</span>
            <span className="text-lg font-black tracking-tight text-white">{val}</span>
        </div>
    );
};

const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
        return (
            <div className="bg-[#1e293b] border border-white/10 p-4 rounded-2xl shadow-2xl">
                <p className="text-[10px] font-black text-slate-500 uppercase mb-1">{payload[0].payload.time}</p>
                <p className="text-sm font-mono font-black text-blue-400">${payload[0].value.toLocaleString()}</p>
            </div>
        );
    }
    return null;
};

const LoadingScreen = () => (
    <div className="h-screen w-full bg-[#0a0f1c] flex flex-col items-center justify-center">
        <div className="w-16 h-16 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin mb-6"></div>
        <p className="text-blue-500 font-black text-[10px] uppercase tracking-[0.4em] animate-pulse">Syncing Sentinel Network</p>
    </div>
);

export default Dashboard;