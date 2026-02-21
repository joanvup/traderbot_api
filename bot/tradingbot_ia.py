import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import numpy as np
import os, time, joblib, warnings, threading
from datetime import datetime, timedelta
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from sklearn.ensemble import RandomForestClassifier
from database_manager import DatabaseManager

# --- CONFIGURACIÓN ELITE v6.1 ---
warnings.filterwarnings("ignore", category=UserWarning)
MODEL_DIR = "memoria_ia"
if not os.path.exists(MODEL_DIR): os.makedirs(MODEL_DIR)

MAX_ACTIVOS = 15
MAX_POSICIONES_GLOBALES = 3
MAGIC_NUMBER = 77193582
TIMEFRAME = mt5.TIMEFRAME_H1
PROBABILIDAD_IA_MINIMA = 0.76

# PROTECCIÓN ACTIVA (VALORES OPTIMIZADOS)
BE_THRESHOLD = 1.0  # Mover a 0 riesgo cuando ganancia = 1x ATR
TS_DISTANCE = 1.5   # Perseguir precio a 1.5x ATR
ATR_MULTI_SL = 1.5  # Stop Loss inicial
ATR_MULTI_TP = 4.0  # Take Profit inicial
FEATURES = ['rsi', 'ema_l', 'ema_r', 'volatilidad']

db = DatabaseManager(host="192.168.3.5", user="bot_user", password="S0portefcbv", database="traderbot_db")
LOG_BUFFER = []
MODELOS_IA = {}

def agregar_log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    LOG_BUFFER.append(f"[{t}] {msg}")
    if len(LOG_BUFFER) > 12: LOG_BUFFER.pop(0)

# ==========================================
# MOTOR DE DEFENSA ACTIVA
# ==========================================

def gestionar_proteccion_activa(posiciones, magic_number):
    for p in posiciones:
        if p.magic != magic_number: continue
        symbol = p.symbol
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 0, 20)
        if rates is None: continue
        df_atr = pd.DataFrame(rates)
        atr = ta.atr(df_atr['high'], df_atr['low'], df_atr['close'], length=14).iloc[-1]
        
        nuevo_sl = p.sl
        modificar = False
        
        if p.type == 0: # BUY
            # 1. Break-Even
            if (p.price_current - p.price_open) > (atr * BE_THRESHOLD) and p.sl < p.price_open:
                nuevo_sl = p.price_open + (atr * 0.1)
                modificar = True
                agregar_log(f"🛡️ BE BUY: {symbol}")
            # 2. Trailing Stop
            target_ts = p.price_current - (atr * TS_DISTANCE)
            if target_ts > nuevo_sl:
                nuevo_sl = target_ts
                modificar = True
        else: # SELL
            # 1. Break-Even
            if (p.price_open - p.price_current) > (atr * BE_THRESHOLD) and (p.sl > p.price_open or p.sl == 0):
                nuevo_sl = p.price_open - (atr * 0.1)
                modificar = True
                agregar_log(f"🛡️ BE SELL: {symbol}")
            # 2. Trailing Stop
            target_ts = p.price_current + (atr * TS_DISTANCE)
            if nuevo_sl == 0 or target_ts < nuevo_sl:
                nuevo_sl = target_ts
                modificar = True

        if modificar:
            request = {"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "sl": nuevo_sl, "tp": p.tp}
            mt5.order_send(request)

# ==========================================
# LÓGICA DE TRADING E IA
# ==========================================

def tarea_entrenamiento(symbol):
    try:
        if not mt5.initialize(): return symbol, None
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 0, 2000)
        if rates is None: return symbol, None
        df = pd.DataFrame(rates)
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema_l'], df['ema_r'] = ta.ema(df['close'], 200), ta.ema(df['close'], 50)
        df['volatilidad'] = df['high'] - df['low']
        df['target'] = (df['close'].shift(-3) > df['close']).astype(int)
        df = df.dropna()
        X, y = df[FEATURES], df['target']
        modelo = RandomForestClassifier(n_estimators=100, max_depth=10).fit(X, y)
        return symbol, modelo
    except: return symbol, None

def abrir_orden(tipo, symbol, atr):
    lot = 0.01 if any(x in symbol for x in ["BTC", "XAU", "ETH", "NAS"]) else 0.1
    tick = mt5.symbol_info_tick(symbol)
    s_info = mt5.symbol_info(symbol)
    precio = tick.ask if tipo == "COMPRA" else tick.bid
    fill = mt5.ORDER_FILLING_FOK if s_info.filling_mode & 1 else mt5.ORDER_FILLING_IOC
    request = {
        "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": lot,
        "type": mt5.ORDER_TYPE_BUY if tipo == "COMPRA" else mt5.ORDER_TYPE_SELL,
        "price": precio, "magic": MAGIC_NUMBER,
        "sl": precio - (atr*ATR_MULTI_SL) if tipo=="COMPRA" else precio + (atr*ATR_MULTI_SL),
        "tp": precio + (atr*ATR_MULTI_TP) if tipo=="COMPRA" else precio - (atr*ATR_MULTI_TP),
        "type_filling": fill, "type_time": mt5.ORDER_TIME_GTC
    }
    mt5.order_send(request)
    agregar_log(f"🚀 {tipo} {symbol}")

if __name__ == "__main__":
    # 1. Inicialización con reintentos
    if not mt5.initialize():
        print("Fallo al iniciar MT5"); quit()
    
    # 2. Verificación de cuenta
    account_info = mt5.account_info()
    if account_info is None:
        print("❌ ERROR: No se detectó cuenta de Libertex conectada. Abre MT5 y loguéate."); quit()
    else:
        print(f"✅ Conectado a Libertex - Cuenta: {account_info.login}")

    print("Auditoría de datos..."); db.sincronizar_trades(MAGIC_NUMBER)
    
    # 3. Obtención de activos con manejo de errores (Libertex Fix)
    print("Obteniendo lista de activos...")
    todos_los_simbolos = mt5.symbols_get()
    
    if todos_los_simbolos is None:
        print("❌ Error: No se recibieron símbolos. Reintenta en 5 segundos...")
        time.sleep(5)
        todos_los_simbolos = mt5.symbols_get()

    if todos_los_simbolos is not None:
        # Libertex usa nombres como EURUSD o EURUSD_ (con guión). 
        # Buscamos coincidencias parciales.
        keywords = ["USD", "BTC", "XAU", "NAS", "GOLD", "ETH"]
        activos = [s.name for s in todos_los_simbolos if s.visible and any(k in s.name.upper() for k in keywords)]
        activos = activos[:MAX_ACTIVOS]
        print(f"👍 Activos encontrados en Libertex: {activos}")
    else:
        print("❌ No se pudieron cargar activos. Asegúrate de dar clic derecho en Market Watch -> 'Show All'")
        quit()

    # 4. Entrenamiento (Igual que antes)
    with ProcessPoolExecutor() as ex:
        for sym, mod in ex.map(tarea_entrenamiento, activos):
            if mod: MODELOS_IA[sym] = mod

    db_pool = ThreadPoolExecutor(max_workers=2)
    while True:
        try:
            acc = mt5.account_info()
            pos = mt5.positions_get(magic=MAGIC_NUMBER)
            if pos: gestionar_proteccion_activa(pos, MAGIC_NUMBER)
            db.actualizar_posiciones_vivas(pos, MAGIC_NUMBER)

            dash = []
            for s in activos:
                rates = mt5.copy_rates_from_pos(s, TIMEFRAME, 0, 300)
                if rates is None or s not in MODELOS_IA: continue
                df = pd.DataFrame(rates)
                df['rsi'], df['ema_l'], df['atr'] = ta.rsi(df['close'], 14), ta.ema(df['close'], 200), ta.atr(df['high'], df['low'], df['close'], 14)
                df['ema_r'], df['volatilidad'] = ta.ema(df['close'], 50), df['high'] - df['low']
                last = df.dropna().iloc[-1]
                
                prob = MODELOS_IA[s].predict_proba(pd.DataFrame([last[FEATURES].values], columns=FEATURES))[0][1]
                
                # Lógica Verbos
                signal, motivo = "ESPERAR", "IA Neutral"
                if prob > PROBABILIDAD_IA_MINIMA:
                    if last['close'] > last['ema_l']: signal = "COMPRA"
                    else: motivo = "EMA Filtro"
                elif prob < (1 - PROBABILIDAD_IA_MINIMA):
                    if last['close'] < last['ema_l']: signal = "VENTA"
                    else: motivo = "EMA Filtro"

                is_open = any(p.symbol == s for p in pos) if pos else False
                if signal != "ESPERAR" and not is_open and len(pos or []) < MAX_POSICIONES_GLOBALES:
                    abrir_orden(signal, s, last['atr'])

                db_pool.submit(db.actualizar_estado_bot, True, acc.balance, acc.equity)
                db_pool.submit(db.sincronizar_trades, MAGIC_NUMBER)
                db_pool.submit(db.actualizar_monitoreo, s, float(last['close']), float(last['rsi']), float(prob), "ABIERTA" if is_open else signal)
                dash.append({"s":s, "ia":prob, "st": "ABIERTA" if is_open else signal, "m": motivo if signal=="ESPERAR" else "OK"})

            os.system('cls')
            print(f"--- SENTINEL v6.1 | {datetime.now().strftime('%H:%M:%S')} | Balance: {acc.balance} ---")
            for d in dash: print(f"{d['s']:<10} | IA: {d['ia']:.2%} | {d['st']:<10} | {d['m']}")
            for l in reversed(LOG_BUFFER): print(f"> {l}")
            time.sleep(15)
        except Exception as e: print(f"Error: {e}"); time.sleep(10)