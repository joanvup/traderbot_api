import React, { useEffect, useState, useCallback } from 'react';
import api from './api/axios';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';
import { TrendingUp, TrendingDown, DollarSign, Activity, LogOut, RefreshCw, Clock, Cpu, Zap, ShieldCheck } from 'lucide-react';
import jsPDF from 'jspdf';
import 'jspdf-autotable';
import { Download, FileText, Table as TableIcon } from 'lucide-react';

const Dashboard = ({ onLogout }) => {
    const [summary, setSummary] = useState(null);
    const [history, setHistory] = useState([]);
    const [trades, setTrades] = useState([]);
    const [monitoring, setMonitoring] = useState([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [lastUpdate, setLastUpdate] = useState(new Date());

    const fetchData = useCallback(async (isManual = false) => {
        if (isManual) setRefreshing(true);
        try {
            const [s, h, t, m] = await Promise.all([
                api.get('/stats/summary'),
                api.get('/stats/history'),
                api.get('/stats/trades'),
                api.get('/stats/monitoring')
            ]);
            setSummary(s.data); setHistory(h.data); setTrades(t.data); setMonitoring(m.data);
            setLastUpdate(new Date());
        } catch (err) { console.error(err); }
        finally { setLoading(false); setRefreshing(false); }
    }, []);

    const exportPDF = () => {
        const doc = new jsPDF();
        doc.setFontSize(20);
        doc.text("TraderBot v5.0 - Reporte de Rendimiento", 14, 22);
        doc.setFontSize(11);
        doc.text(`Fecha: ${new Date().toLocaleString()}`, 14, 30);
        doc.text(`Profit Total: $${summary.total_profit}`, 14, 38);

        const tableRows = trades.map(t => [
            t.symbol, t.type, t.profit.toFixed(2), t.close_time
        ]);

        doc.autoTable({
            head: [['Símbolo', 'Tipo', 'Profit ($)', 'Fecha']],
            body: tableRows,
            startY: 45,
            theme: 'grid'
        });

        doc.save(`Reporte_TraderBot_${new Date().getTime()}.pdf`);
    };

    const exportCSV = async () => {
        try {
            const response = await api.get('/export/csv', { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'historial_trades.csv');
            document.body.appendChild(link);
            link.click();
        } catch (err) { console.error("Error al exportar CSV", err); }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(() => fetchData(), 15000);
        return () => clearInterval(interval);
    }, [fetchData]);

    if (loading) return <LoadingScreen />;

    return (
        <div className="min-h-screen bg-[#0a0f1c] text-slate-100 font-sans selection:bg-blue-500/30">
            {/* Header Pro */}
            <nav className="bg-[#0f172a]/80 backdrop-blur-xl border-b border-white/5 px-6 py-4 sticky top-0 z-50 flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <div className="bg-gradient-to-br from-blue-500 to-indigo-600 p-2.5 rounded-2xl shadow-lg shadow-blue-500/20">
                        <Cpu size={22} className="text-white animate-pulse" />
                    </div>
                    <div>
                        <h1 className="font-black text-lg tracking-tight uppercase italic text-transparent bg-clip-text bg-gradient-to-r from-white to-slate-400">AI Sentinel <span className="text-blue-500">v5.0</span></h1>
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
                        <LogOut size={20} />
                    </button>
                </div>
            </nav>

            <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">

                {/* Métricas Principales */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <KPI icon={<DollarSign />} label="Balance" val={`$${summary.current_balance.toLocaleString()}`} color="blue" />
                    <KPI icon={<TrendingUp />} label="Net Profit" val={`$${summary.total_profit.toLocaleString()}`} color="emerald" />
                    <KPI icon={<Zap />} label="Win Rate" val={`${summary.win_rate}%`} color="violet" />
                    <KPI icon={<Activity />} label="Trades" val={summary.total_trades} color="amber" />
                </div>

                {/* SECCIÓN DE VIGILANCIA IA - Lo solicitado */}
                <section>
                    <div className="flex items-center gap-2 mb-4 px-1">
                        <ShieldCheck className="text-blue-500" size={20} />
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

                {/* Diario de Operaciones */}
                <div className="bg-[#0f172a] border border-white/5 rounded-[2.5rem] overflow-hidden">
                    <div className="p-6 border-b border-white/5 flex justify-between items-center bg-white/[0.02]">
                        <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">Live Execution Log</h3>
                        <div className="flex gap-2">
                            <button onClick={exportCSV} className="p-2 rounded-xl bg-white/5 text-slate-400 hover:text-white transition-all">
                                <TableIcon size={18} />
                            </button>
                            <button onClick={exportPDF} className="p-2 rounded-xl bg-white/5 text-slate-400 hover:text-white transition-all">
                                <FileText size={18} />
                            </button>
                        </div>
                    </div>
                    <div className="divide-y divide-white/5">
                        {trades.map(t => (
                            <div key={t.id} className="p-5 flex items-center justify-between hover:bg-white/[0.02] transition-all">
                                <div className="flex items-center gap-4">
                                    <div className={`p-3 rounded-2xl ${t.profit > 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                                        {t.profit > 0 ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                                    </div>
                                    <div>
                                        <div className="font-black text-sm">{t.symbol}</div>
                                        <div className="text-[10px] font-bold text-slate-500 uppercase">{t.type} • {t.close_time}</div>
                                    </div>
                                </div>
                                <div className={`font-mono font-bold ${t.profit > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                    {t.profit > 0 ? '+' : ''}{t.profit.toFixed(2)}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </main>
        </div>
    );
};

// --- SUBCOMPONENTES ---

const MarketCard = ({ data }) => {
    const isBullish = data.ia_prob > 0.5;
    return (
        <div className="bg-[#0f172a] border border-white/5 p-5 rounded-3xl relative overflow-hidden group hover:border-blue-500/30 transition-all">
            <div className={`absolute top-0 right-0 w-24 h-24 blur-3xl opacity-10 ${isBullish ? 'bg-emerald-500' : 'bg-red-500'}`}></div>
            <div className="flex justify-between items-start mb-4">
                <div>
                    <h4 className="font-black text-slate-100">{data.symbol}</h4>
                    <p className="text-xs font-mono text-slate-500">${data.price.toFixed(data.symbol.includes('BTC') ? 2 : 4)}</p>
                </div>
                <div className={`px-2 py-1 rounded-lg text-[9px] font-black uppercase ${data.status === 'ABIERTA' ? 'bg-blue-500/20 text-blue-400' : 'bg-white/5 text-slate-500'}`}>
                    {data.status}
                </div>
            </div>

            <div className="space-y-3">
                <div className="flex justify-between items-end">
                    <span className="text-[10px] font-bold text-slate-500 uppercase">AI Confidence</span>
                    <span className={`text-lg font-mono font-black ${isBullish ? 'text-emerald-400' : 'text-red-400'}`}>
                        {(data.ia_prob * 100).toFixed(1)}%
                    </span>
                </div>
                {/* Barra de Probabilidad Estilo Pro */}
                <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                    <div
                        className={`h-full transition-all duration-1000 ${isBullish ? 'bg-emerald-500' : 'bg-red-500'}`}
                        style={{ width: `${data.ia_prob * 100}%` }}
                    ></div>
                </div>
                <div className="flex justify-between text-[10px] font-bold text-slate-600 uppercase">
                    <span>RSI: {data.rsi.toFixed(1)}</span>
                    <span>{isBullish ? 'Strong Buy Bias' : 'Strong Sell Bias'}</span>
                </div>
            </div>
        </div>
    );
};

const KPI = ({ icon, label, val, color }) => {
    const colors = {
        blue: "text-blue-400", emerald: "text-emerald-400", violet: "text-violet-400", amber: "text-amber-400"
    };
    return (
        <div className="bg-[#0f172a] border border-white/5 p-5 rounded-[2rem] flex flex-col items-center text-center">
            <div className={`mb-2 ${colors[color]}`}>{icon}</div>
            <span className="text-[9px] font-black uppercase tracking-tighter text-slate-500 mb-1">{label}</span>
            <span className="text-lg font-black tracking-tight">{val}</span>
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
        <div className="w-16 h-16 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin mb-4"></div>
        <p className="text-blue-500 font-black text-xs uppercase tracking-[0.3em] animate-pulse">Initializing Sentinel AI</p>
    </div>
);

export default Dashboard;