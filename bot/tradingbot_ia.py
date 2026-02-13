import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import numpy as np
import os
import time
import joblib
import warnings
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from database_manager import DatabaseManager

# Configura tus credenciales de MySQL Community
db = DatabaseManager(
    host="localhost",
    user="user_bot",
    password="S0portefcbv",
    database="traderbot_db"
)

# --- SILENCIAR ALERTAS Y CONFIGURACIÓN DE RUTAS ---
warnings.filterwarnings("ignore", category=UserWarning)
MODEL_DIR = "memoria_ia"
if not os.path.exists(MODEL_DIR): os.makedirs(MODEL_DIR)

# ==========================================
# 1. CONFIGURACIÓN DE ALTO RENDIMIENTO (v4.0)
# ==========================================
MAX_ACTIVOS = 15
MAX_POSICIONES_GLOBALES = 5
MAGIC_NUMBER = 20260213
TIMEFRAME = mt5.TIMEFRAME_H1       # <-- Cambiado a H1 para estabilidad
PROBABILIDAD_IA_MINIMA = 0.72      # <-- Filtro de confianza estricto
RE_TRAIN_HOURS = 24

# Parámetros de Riesgo Asimétrico
ATR_MULTI_SL = 3.0  
ATR_MULTI_TP = 6.0  
FEATURES = ['rsi', 'ema_l', 'ema_r', 'volatilidad']

LOG_BUFFER = []

def agregar_log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    LOG_BUFFER.append(f"[{t}] {msg}")
    if len(LOG_BUFFER) > 10: LOG_BUFFER.pop(0)

# ==========================================
# 2. MOTOR DE INTELIGENCIA ARTIFICIAL
# ==========================================

def entrenar_cerebro_ia(symbol):
    try:
        # Descargamos 2500 velas para un entrenamiento profundo
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 0, 2500)
        if rates is None or len(rates) < 1000: return None
        
        df = pd.DataFrame(rates)
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema_l'] = ta.ema(df['close'], length=200)
        df['ema_r'] = ta.ema(df['close'], length=50)
        df['volatilidad'] = df['high'] - df['low']
        # Target: ¿El precio subió en las siguientes 3 velas?
        df['target'] = (df['close'].shift(-3) > df['close']).astype(int)
        df = df.dropna()
        
        X = df[FEATURES]
        y = df['target']
        
        modelo = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        modelo.fit(X, y)
        
        ruta = os.path.join(MODEL_DIR, f"{symbol}.joblib")
        joblib.dump(modelo, ruta)
        return modelo
    except Exception as e:
        agregar_log(f"IA Error {symbol}: {e}")
        return None

def cargar_o_evolucionar(symbol):
    ruta = os.path.join(MODEL_DIR, f"{symbol}.joblib")
    if os.path.exists(ruta):
        fecha_mod = datetime.fromtimestamp(os.path.getmtime(ruta))
        if (datetime.now() - fecha_mod) < timedelta(hours=RE_TRAIN_HOURS):
            return joblib.load(ruta), "CARGADO"
        else:
            agregar_log(f"Evolucionando {symbol}...")
            return entrenar_cerebro_ia(symbol), "EVOLUCIONADO"
    return entrenar_cerebro_ia(symbol), "NUEVO"

# ==========================================
# 3. GESTIÓN DE ÓRDENES (COMPATIBILIDAD TOTAL)
# ==========================================

def abrir_orden(tipo, symbol, atr):
    try:
        # Lote inteligente por activo
        lotaje = 0.01 if any(x in symbol for x in ["BTC", "XAU", "ETH"]) else 0.1
        tick = mt5.symbol_info_tick(symbol)
        s_info = mt5.symbol_info(symbol)
        if not tick or not s_info: return
        
        precio = tick.ask if tipo == "COMPRA" else tick.bid
        
        # FIX: Filling Mode usando bits (1=FOK, 2=IOC)
        if s_info.filling_mode & 1: fill = mt5.ORDER_FILLING_FOK
        elif s_info.filling_mode & 2: fill = mt5.ORDER_FILLING_IOC
        else: fill = mt5.ORDER_FILLING_RETURN

        sl = atr * ATR_MULTI_SL
        tp = atr * ATR_MULTI_TP

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lotaje,
            "type": mt5.ORDER_TYPE_BUY if tipo == "COMPRA" else mt5.ORDER_TYPE_SELL,
            "price": precio,
            "magic": MAGIC_NUMBER,
            "sl": precio - sl if tipo == "COMPRA" else precio + sl,
            "tp": precio + tp if tipo == "COMPRA" else precio - tp,
            "type_filling": fill,
            "type_time": mt5.ORDER_TIME_GTC,
        }
        
        res = mt5.order_send(request)
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            agregar_log(f"¡ENTRADA! {tipo} en {symbol}")
        else:
            agregar_log(f"RECHAZO {symbol}: {res.comment}")
    except Exception as e:
        agregar_log(f"Error Ejecución {symbol}: {e}")

# ==========================================
# 4. LOOP PRINCIPAL Y DASHBOARD
# ==========================================

MODELOS_IA = {}

if __name__ == "__main__":
    if not mt5.initialize():
        print("Error MT5"); quit()
        
    # Selección dinámica de activos
    activos = [s.name for s in mt5.symbols_get() if s.visible and ("USD" in s.name or "BTC" in s.name or "XAU" in s.name)][:MAX_ACTIVOS]
    
    for s in activos:
        mod, status = cargar_o_evolucionar(s)
        MODELOS_IA[s] = mod
        agregar_log(f"{s}: Cerebro {status}")

    while True:
        try:
            acc = mt5.account_info()
            # --- NUEVA LÓGICA DE TELEMETRÍA ---
            # 1. Actualizar estado para la Web
            db.actualizar_estado_bot(
                is_active=True, 
                balance=acc.balance, 
                equity=acc.equity
            )
        
            # 2. Sincronizar historial de trades para las gráficas
            db.sincronizar_trades(MAGIC_NUMBER)

            dashboard = []
            posiciones = mt5.positions_get(magic=MAGIC_NUMBER)
            num_pos = len(posiciones) if posiciones else 0
            
            for s in activos:
                rates = mt5.copy_rates_from_pos(s, TIMEFRAME, 0, 300)
                if rates is None or len(rates) < 200: continue
                
                df = pd.DataFrame(rates)
                df['rsi'] = ta.rsi(df['close'], length=14)
                df['ema_l'] = ta.ema(df['close'], length=200)
                df['ema_r'] = ta.ema(df['close'], length=50)
                df['volatilidad'] = df['high'] - df['low']
                df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
                df = df.dropna()
                
                if df.empty: continue
                last = df.iloc[-1]
                
                # --- FILTRO DE VOLATILIDAD ---
                atr_promedio = df['atr'].tail(20).mean()
                mercado_vivo = last['atr'] > (atr_promedio * 0.8)

                # --- PREDICCIÓN IA ---
                prob = 0.5
                if MODELOS_IA.get(s):
                    input_ia = pd.DataFrame([last[FEATURES].values], columns=FEATURES)
                    prob = MODELOS_IA[s].predict_proba(input_ia)[0][1]

                # --- LÓGICA DE SEÑAL ---
                señal = "ESPERAR"
                if mercado_vivo:
                    if last['close'] > last['ema_l'] and last['rsi'] > 45 and prob > PROBABILIDAD_IA_MINIMA:
                        señal = "COMPRA"
                    elif last['close'] < last['ema_l'] and last['rsi'] < 55 and prob < (1 - PROBABILIDAD_IA_MINIMA):
                        señal = "VENTA"
                
                abierta = any(p.symbol == s for p in posiciones) if posiciones else False
                if señal != "ESPERAR" and not abierta and num_pos < MAX_POSICIONES_GLOBALES:
                    abrir_orden(señal, s, last['atr'])
                    num_pos += 1
                
                dashboard.append({"s": s, "p": last['close'], "ia": prob, "st": "ABIERTA" if abierta else señal})

            # Imprimir Dashboard Pro
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"--- GLOBAL SENTINEL v4.0 (AI + H1) | {datetime.now().strftime('%H:%M:%S')} ---")
            print(f"Equity: {acc.equity:.2f} | Posiciones: {num_pos}/{MAX_POSICIONES_GLOBALES} | AlgoTrading: {acc.trade_allowed}")
            print("-" * 75)
            print(f"{'SYMBOL':<12} | {'PRECIO':<10} | {'IA PROB':<10} | {'ESTADO':<10}")
            print("-" * 75)
            for d in dashboard:
                print(f"{d['s']:<12} | {d['p']:<10.4f} | {d['ia']:.2%} | {d['st']}")
            print("-" * 75)
            print(" LOG DE EVENTOS:")
            for l in reversed(LOG_BUFFER): print(f"> {l}")
            
            time.sleep(15)

        except Exception as e:
            # Si el bot falla, intentamos reportar que está inactivo
            db.actualizar_estado_bot(False, 0, 0)
            print(f"Error: {e}")
            time.sleep(10)