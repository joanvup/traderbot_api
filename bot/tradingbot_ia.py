import MetaTrader5 as mt5
import pandas as pd
import pandas_ta as ta
import numpy as np
import os
import time
import joblib
import warnings
import threading
from datetime import datetime, timedelta
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from sklearn.ensemble import RandomForestClassifier
from database_manager import DatabaseManager

# --- CONFIGURACIÓN DE SEGURIDAD ---
warnings.filterwarnings("ignore", category=UserWarning)
MODEL_DIR = "memoria_ia"
if not os.path.exists(MODEL_DIR): os.makedirs(MODEL_DIR)

# --- CONFIGURACIÓN DE ALTO RENDIMIENTO (v5.0 PRO) ---
MAX_ACTIVOS = 30                 # Escalado a 30 mercados
MAX_POSICIONES_GLOBALES = 2     # Aumentado el límite de riesgo controlado
MAGIC_NUMBER = 20260213
TIMEFRAME = mt5.TIMEFRAME_H1
PROBABILIDAD_IA_MINIMA = 0.82
RE_TRAIN_HOURS = 24

# Parámetros de Riesgo
ATR_MULTI_SL = 1.0
ATR_MULTI_TP = 3.0
FEATURES = ['rsi', 'ema_l', 'ema_r', 'volatilidad']

# Inicialización de DB
db = DatabaseManager(
    host="192.168.3.5",
    user="bot_user",
    password="S0portefcbv",
    database="traderbot_db"
)

LOG_BUFFER = []
MODELOS_IA = {}

def agregar_log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    LOG_BUFFER.append(f"[{t}] {msg}")
    if len(LOG_BUFFER) > 12: LOG_BUFFER.pop(0)

# ==========================================
# 1. MOTOR DE IA CON PARALELISMO
# ==========================================

def tarea_entrenamiento(symbol):
    """Función independiente para ser ejecutada por ProcessPoolExecutor"""
    try:
        # Re-inicializar MT5 en cada proceso hijo (necesario para Multiprocessing)
        if not mt5.initialize():
            return symbol, None, "Error MT5"
            
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 0, 2500)
        if rates is None or len(rates) < 1000:
            return symbol, None, "Datos insuficientes"
        
        df = pd.DataFrame(rates)
        df['rsi'] = ta.rsi(df['close'], length=14)
        df['ema_l'] = ta.ema(df['close'], length=200)
        df['ema_r'] = ta.ema(df['close'], length=50)
        df['volatilidad'] = df['high'] - df['low']
        df['target'] = (df['close'].shift(-3) > df['close']).astype(int)
        df = df.dropna()
        
        X = df[FEATURES]
        y = df['target']
        
        modelo = RandomForestClassifier(n_estimators=100, max_depth=10, n_jobs=1)
        modelo.fit(X, y)
        
        ruta = os.path.join(MODEL_DIR, f"{symbol}.joblib")
        joblib.dump(modelo, ruta)
        return symbol, modelo, "EXITO"
    except Exception as e:
        return symbol, None, str(e)

def inicializar_cerebros_paralelos(activos):
    """Entrena todos los modelos usando múltiples núcleos de CPU"""
    global MODELOS_IA
    agregar_log(f"Iniciando entrenamiento paralelo de {len(activos)} activos...")
    
    # Usamos ProcessPool para bypass del GIL de Python y máxima velocidad
    with ProcessPoolExecutor() as executor:
        resultados = list(executor.map(tarea_entrenamiento, activos))
    
    for symbol, modelo, status in resultados:
        if modelo:
            MODELOS_IA[symbol] = modelo
            # No agregamos log de cada uno para no saturar, solo si hay error
        else:
            agregar_log(f"Error {symbol}: {status}")

# ==========================================
# 2. TELEMETRÍA ASÍNCRONA (No bloqueante)
# ==========================================

def update_db_async(symbol, last, prob, estado, acc):
    """Envía datos a MySQL en un hilo separado para no ralentizar el trading"""
    try:
        # Actualizar estado general
        db.actualizar_estado_bot(True, acc.balance, acc.equity)
        # Sincronizar historial
        db.sincronizar_trades(MAGIC_NUMBER)
        # Actualizar monitoreo de activo
        db.actualizar_monitoreo(
            symbol=symbol, 
            price=float(last['close']), 
            rsi=float(last['rsi']), 
            ia_prob=float(prob), 
            status=estado
        )
    except Exception as e:
        pass # Los errores de DB no deben tumbar al bot

# ==========================================
# 3. GESTIÓN DE ÓRDENES Y RIESGO
# ==========================================

def abrir_orden(tipo, symbol, atr):
    try:
        # Verificación de Margen Libre (Seguridad Financiera)
        acc = mt5.account_info()
        if acc.margin_free < (acc.balance * 0.05): # Si el margen libre es < 5% del balance
            agregar_log(f"Margen insuficiente para {symbol}")
            return

        lotaje = 0.01 if any(x in symbol for x in ["BTC", "XAU", "ETH", "NAS", "US30"]) else 0.1
        tick = mt5.symbol_info_tick(symbol)
        s_info = mt5.symbol_info(symbol)
        if not tick or not s_info: return
        
        precio = tick.ask if tipo == "COMPRA" else tick.bid
        fill = mt5.ORDER_FILLING_FOK if s_info.filling_mode & 1 else mt5.ORDER_FILLING_IOC

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lotaje,
            "type": mt5.ORDER_TYPE_BUY if tipo == "COMPRA" else mt5.ORDER_TYPE_SELL,
            "price": precio,
            "magic": MAGIC_NUMBER,
            "sl": precio - (atr * ATR_MULTI_SL) if tipo == "COMPRA" else precio + (atr * ATR_MULTI_SL),
            "tp": precio + (atr * ATR_MULTI_TP) if tipo == "COMPRA" else precio - (atr * ATR_MULTI_TP),
            "type_filling": fill,
            "type_time": mt5.ORDER_TIME_GTC,
        }
        
        res = mt5.order_send(request)
        if res.retcode == mt5.TRADE_RETCODE_DONE:
            agregar_log(f"¡TRADE! {tipo} {symbol}")
        else:
            agregar_log(f"RECHAZO {symbol}: {res.comment}")
    except Exception as e:
        agregar_log(f"Err Ejecución: {e}")

# ==========================================
# 4. LOOP DE ALTO RENDIMIENTO
# ==========================================

if __name__ == "__main__":
    if not mt5.initialize():
        print("Error inicializando MT5"); quit()
        
    # Selección de activos
    activos = [s.name for s in mt5.symbols_get() if s.visible and ("USD" in s.name or "BTC" in s.name or "XAU" in s.name or "ETH" in s.name or "NAS" in s.name)][:MAX_ACTIVOS]
    
    # Entrenamiento inicial (Paralelo)
    inicializar_cerebros_paralelos(activos)
    
    # Executor para hilos de DB
    db_thread_executor = ThreadPoolExecutor(max_workers=2)

    while True:
        try:
            acc = mt5.account_info()
            posiciones = mt5.positions_get(magic=MAGIC_NUMBER)
            num_pos = len(posiciones) if posiciones else 0
            dashboard = []

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
                
                # Predicción IA
                input_ia = pd.DataFrame([last[FEATURES].values], columns=FEATURES)
                prob = MODELOS_IA[s].predict_proba(input_ia)[0][1] if s in MODELOS_IA else 0.5
                
                # Señal (Con Filtro de Volatilidad integrado)
                atr_avg = df['atr'].tail(20).mean()
                señal = "ESPERAR"
                if last['atr'] > (atr_avg * 0.8):
                    if last['close'] > last['ema_l'] and last['rsi'] > 45 and prob > PROBABILIDAD_IA_MINIMA:
                        señal = "COMPRA"
                    elif last['close'] < last['ema_l'] and last['rsi'] < 55 and prob < (1 - PROBABILIDAD_IA_MINIMA):
                        señal = "VENTA"
                
                abierta = any(p.symbol == s for p in posiciones) if posiciones else False
                estado_web = "ABIERTA" if abierta else señal

                # Ejecución de Trades
                if señal != "ESPERAR" and not abierta and num_pos < MAX_POSICIONES_GLOBALES:
                    abrir_orden(señal, s, last['atr'])
                    num_pos += 1
                
                # Enviar Telemetría (SIN BLOQUEAR EL LOOP)
                db_thread_executor.submit(update_db_async, s, last, prob, estado_web, acc)
                
                dashboard.append({"s": s, "p": last['close'], "ia": prob, "st": estado_web})

            # Dashboard en Consola (Actualizado cada ciclo)
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"--- SENTINEL v5.0 PRO | {datetime.now().strftime('%H:%M:%S')} | ACT: {len(activos)} ---")
            print(f"Equity: {acc.equity:.2f} | Posiciones: {num_pos}/{MAX_POSICIONES_GLOBALES} | DB: Online")
            print("-" * 75)
            for d in dashboard[:15]: # Mostramos los primeros 15 en consola para no saturar
                print(f"{d['s']:<12} | {d['p']:<10.4f} | {d['ia']:.2%} | {d['st']}")
            print(f"... y {len(dashboard)-15} activos más en monitoreo web.")
            print("-" * 75)
            print(" ÚLTIMOS LOGS:")
            for l in reversed(LOG_BUFFER): print(f"> {l}")
            
            time.sleep(10) # Ciclo de alta frecuencia (10 segundos)

        except Exception as e:
            print(f"Error Crítico: {e}")
            time.sleep(10)