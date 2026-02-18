import React, { useEffect, useState, useCallback } from 'react';
import api from './api/axios';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import {
    TrendingUp, TrendingDown, DollarSign, Activity, LogOut, RefreshCw,
    Clock, Cpu, Zap, ShieldCheck, FileText, Table as TableIcon,
    ChevronLeft, ChevronRight
} from 'lucide-react';
import jsPDF from 'jspdf';
import 'jspdf-autotable';

const Dashboard = ({ onLogout }) => {
    // Estados de datos
    const [summary, setSummary] = useState(null);
    const [history, setHistory] = useState([]);
    const [trades, setTrades] = useState([]);
    const [monitoring, setMonitoring] = useState([]);

    // Estados de UI y Paginación
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [lastUpdate, setLastUpdate] = useState(new Date());
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const tradesPerPage = 10;

    // Función Principal de Carga de Datos
    const fetchData = useCallback(async (isManual = false) => {
        if (isManual) setRefreshing(true);
        try {
            // Llamadas paralelas para optimizar velocidad
            const [resSum, resHis, resTra, resMon] = await Promise.all([
                api.get('/stats/summary'),
                api.get('/stats/history'),
                api.get(`/stats/trades?page=${currentPage}&limit=${tradesPerPage}`),
                api.get('/stats/monitoring')
            ]);

            setSummary(resSum.data);
            setHistory(resHis.data);
            setTrades(resTra.data.trades);
            setTotalPages(Math.ceil(resTra.data.total_trades / tradesPerPage));
            setMonitoring(resMon.data);
            setLastUpdate(new Date());
        } catch (err) {
            console.error("Error en la sincronización de datos:", err);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [currentPage]);

    // Efecto de refresco automático
    useEffect(() => {
        fetchData();
        const interval = setInterval(() => fetchData(), 15000); // 15 segundos
        return () => clearInterval(interval);
    }, [fetchData]);

    // Manejadores de Paginación
    const handlePrevPage = () => {
        if (currentPage > 1) setCurrentPage(currentPage - 1);
    };

    const handleNextPage = () => {
        if (currentPage < totalPages) setCurrentPage(currentPage + 1);
    };

    // Funciones de Exportación
    const exportPDF = () => {
        const doc = new jsPDF();
        doc.setFontSize(18);
        doc.text("SENTINEL AI - REPORTE DE TRADING", 14, 20);
        doc.setFontSize(10);
        doc.text(`Generado el: ${new Date().toLocaleString()}`, 14, 28);
        doc.text(`Balance Actual: $${summary.current_balance}`, 14, 34);
        doc.text(`Profit Neto: $${summary.total_profit}`, 14, 40);

        const tableBody = trades.map(t => [
            t.symbol, t.type, t.lotage, t.profit.toFixed(2), t.open_time, t.close_time
        ]);

        doc.autoTable({
            head: [['Activo', 'Tipo', 'Lote', 'Profit', 'Apertura', 'Cierre']],
            body: tableBody,
            startY: 45,
            theme: 'striped'
        });

        doc.save(`Sentinel_Report_${new Date().getTime()}.pdf`);
    };

    const exportCSV = async () => {
        try {
            const response = await api.get('/export/csv', { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'traderbot_history.csv');
            document.body.appendChild(link);
            link.click();
        } catch (err) {
            alert("Error al descargar CSV");
        }
    };

    if (loading) return <LoadingScreen />;

    return (
        <div className="min-h-screen bg-[#0a0f1c] text-slate-100 font-sans">
            {/* BARRA DE NAVEGACIÓN */}
            <nav className="bg-[#0f172a]/80 backdrop-blur-xl border-b border-white/5 px-6 py-4 sticky top-0 z-50 flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <div className="bg-gradient-to-br from-blue-500 to-indigo-600 p-2.5 rounded-2xl shadow-lg shadow-blue-500/20">
                        <Cpu size={22} className="text-white animate-pulse" />
                    </div>
                    <div>
                        <h1 className="font-black text-lg tracking-tight uppercase italic text-transparent bg-clip-text bg-gradient-to-r from-white to-slate-400">
                            AI Sentinel <span className="text-blue-500">v6.0</span>
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

            <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">

                {/* TARJETAS KPI */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <KPI icon={<DollarSign />} label="Balance Real" val={`$${summary?.current_balance?.toLocaleString() || '0.00'}`} color="blue" />
                    <KPI icon={<TrendingUp />} label="Net Profit" val={`$${summary?.total_profit?.toLocaleString() || '0.00'}`} color="emerald" />
                    <KPI icon={<Zap />} label="Win Rate" val={`${summary?.win_rate}%`} color="violet" />
                    <KPI icon={<Activity />} label="Total Trades" val={summary?.total_trades} color="amber" />
                </div>

                {/* VIGILANCIA DE MERCADO (IA MONITORING) */}
                <section>
                    <div className="flex items-center gap-2 mb-4 px-1">
                        <ShieldCheck className="text-blue-500" size={20} />
                        <h2 className="text-sm font-black uppercase tracking-widest text-slate-400">AI Surveillance Unit</h2>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {monitoring.map(m => (
                            <MarketCard key={m.symbol} data={m} />
                        ))}
                    </div>
                </section>

                {/* GRÁFICA DE EQUIDAD */}
                <div className="bg-[#0f172a] border border-white/5 p-6 rounded-[2.5rem] shadow-2xl">
                    <div className="flex justify-between items-center mb-8">
                        <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">Equity Performance History</h3>
                        <div className="text-blue-500 bg-blue-500/10 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-tighter">Live Account</div>
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

                {/* DIARIO DE EJECUCIÓN (TABLA CON PAGINACIÓN) */}
                <div className="bg-[#0f172a] border border-white/5 rounded-[2.5rem] overflow-hidden shadow-2xl mb-12">
                    <div className="p-6 border-b border-white/5 flex justify-between items-center bg-white/[0.02]">
                        <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">Live Execution Log</h3>
                        <div className="flex gap-2">
                            <button onClick={exportCSV} className="p-2 rounded-xl bg-white/5 text-slate-400 hover:text-white transition-all border border-white/5" title="Exportar CSV">
                                <TableIcon size={18} />
                            </button>
                            <button onClick={exportPDF} className="p-2 rounded-xl bg-white/5 text-slate-400 hover:text-white transition-all border border-white/5" title="Generar Reporte PDF">
                                <FileText size={18} />
                            </button>
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
                                <div className="text-right">
                                    <div className={`font-mono font-black ${t.profit > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                        {t.profit > 0 ? '+' : ''}{t.profit.toFixed(2)}
                                    </div>
                                    <div className="text-[9px] font-bold text-slate-600">PROFIT USD</div>
                                </div>
                            </div>
                        )) : (
                            <div className="p-20 text-center text-slate-600 font-bold uppercase tracking-widest text-xs">
                                No se encontraron registros de trading
                            </div>
                        )}
                    </div>

                    {/* CONTROLES DE PAGINACIÓN */}
                    {totalPages > 1 && (
                        <div className="p-4 border-t border-white/5 flex justify-center items-center gap-6 bg-white/[0.01]">
                            <button
                                onClick={handlePrevPage}
                                disabled={currentPage === 1}
                                className="p-2 rounded-xl bg-white/5 text-slate-400 hover:text-blue-400 disabled:opacity-20 disabled:pointer-events-none transition-all"
                            >
                                <ChevronLeft size={24} />
                            </button>
                            <span className="text-xs font-black text-slate-500 uppercase">
                                Página <span className="text-blue-500">{currentPage}</span> de {totalPages}
                            </span>
                            <button
                                onClick={handleNextPage}
                                disabled={currentPage === totalPages}
                                className="p-2 rounded-xl bg-white/5 text-slate-400 hover:text-blue-400 disabled:opacity-20 disabled:pointer-events-none transition-all"
                            >
                                <ChevronRight size={24} />
                            </button>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
};

// --- SUBCOMPONENTES AUXILIARES ---

const KPI = ({ icon, label, val, color }) => {
    const colors = {
        blue: "text-blue-400", emerald: "text-emerald-400", violet: "text-violet-400", amber: "text-amber-400"
    };
    return (
        <div className="bg-[#0f172a] border border-white/5 p-5 rounded-[2rem] flex flex-col items-center text-center shadow-xl">
            <div className={`mb-2 ${colors[color]}`}>{icon}</div>
            <span className="text-[9px] font-black uppercase tracking-widest text-slate-500 mb-1">{label}</span>
            <span className="text-lg font-black tracking-tight">{val}</span>
        </div>
    );
};

const MarketCard = ({ data }) => {
    const isBullish = data.ia_prob > 0.5;
    return (
        <div className="bg-[#0f172a] border border-white/5 p-5 rounded-3xl relative overflow-hidden hover:border-blue-500/30 transition-all shadow-lg group">
            <div className={`absolute top-0 right-0 w-24 h-24 blur-3xl opacity-10 transition-colors ${isBullish ? 'bg-emerald-500' : 'bg-red-500'}`}></div>
            <div className="flex justify-between items-start mb-4">
                <div>
                    <h4 className="font-black text-slate-100 tracking-tight">{data.symbol}</h4>
                    <p className="text-[11px] font-mono text-slate-500">${data.price.toFixed(5)}</p>
                </div>
                <div className={`px-2 py-1 rounded-lg text-[9px] font-black uppercase tracking-tighter ${data.status === 'ABIERTA' ? 'bg-blue-500/20 text-blue-400' : 'bg-white/5 text-slate-600'}`}>
                    {data.status}
                </div>
            </div>

            <div className="space-y-3">
                <div className="flex justify-between items-end">
                    <span className="text-[10px] font-bold text-slate-500 uppercase">AI Reliability</span>
                    <span className={`text-lg font-mono font-black ${isBullish ? 'text-emerald-400' : 'text-red-400'}`}>
                        {(data.ia_prob * 100).toFixed(1)}%
                    </span>
                </div>
                <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                    <div
                        className={`h-full transition-all duration-1000 ${isBullish ? 'bg-emerald-500' : 'bg-red-500'}`}
                        style={{ width: `${data.ia_prob * 100}%` }}
                    ></div>
                </div>
                <div className="flex justify-between text-[10px] font-bold text-slate-600 uppercase tracking-tighter">
                    <span>RSI: {data.rsi.toFixed(1)}</span>
                    <span className={isBullish ? 'text-emerald-900' : 'text-red-900'}>{isBullish ? 'Bullish Bias' : 'Bearish Bias'}</span>
                </div>
            </div>
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