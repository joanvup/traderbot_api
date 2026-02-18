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

# --- CONFIGURACIÓN DE SEGURIDAD Y SILENCIO ---
warnings.filterwarnings("ignore", category=UserWarning)
MODEL_DIR = "memoria_ia"
if not os.path.exists(MODEL_DIR): os.makedirs(MODEL_DIR)

# ==========================================
# 1. PARÁMETROS DE RENDIMIENTO v6.0 EYE OF PROVIDENCE
# ==========================================
MAX_ACTIVOS = 15                 # Los 15 activos más prometedores
MAX_POSICIONES_GLOBALES = 3      # MÁXIMO 3 trades abiertos simultáneamente (Ultra Conservador)
MAGIC_NUMBER = 20260213          # ID único del Bot
TIMEFRAME = mt5.TIMEFRAME_H1      # Velas de 1 hora (Estabilidad y claridad)
PROBABILIDAD_IA_MINIMA = 0.76    # Aumentamos a 76% (Calibración de ELITE)
RE_TRAIN_HOURS = 24              # Re-entrenamiento diario de la IA
RE_SCAN_HOURS = 4                # Re-selección de activos cada 4 horas

# Gestión de Riesgo "Eye of Providence"
ATR_MULTI_SL = 1.5               # Stop Loss justo para cortar pérdidas rápido
ATR_MULTI_TP = 4.0               # Take Profit largo para dejar correr las ganancias (Ratio ~1:2.6)
FEATURES = ['rsi', 'ema_l', 'ema_r', 'volatilidad']

# Configuración de Base de Datos (Ubuntu)
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
# 2. MOTOR DE IA Y SELECCIÓN INTELIGENTE
# ==========================================

def tarea_entrenamiento(symbol):
    try:
        if not mt5.initialize(): return symbol, None, "Error MT5"
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 0, 2500)
        if rates is None or len(rates) < 1000: return symbol, None, "Sin datos"
        
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
        return symbol, modelo, "OK"
    except Exception as e:
        return symbol, None, str(e)

def cargar_o_evolucionar(symbol):
    ruta = os.path.join(MODEL_DIR, f"{symbol}.joblib")
    if os.path.exists(ruta):
        fecha_mod = datetime.fromtimestamp(os.path.getmtime(ruta))
        if (datetime.now() - fecha_mod) < timedelta(hours=RE_TRAIN_HOURS):
            return joblib.load(ruta), "CARGADO"
        else:
            agregar_log(f"Evolucionando {symbol} (Re-entrenamiento)...")
            return tarea_entrenamiento(symbol), "EVOLUCIONADO" # Llama a tarea_entrenamiento directamente
    return tarea_entrenamiento(symbol), "NUEVO"

def inicializar_cerebros_paralelos(activos_lista):
    global MODELOS_IA
    agregar_log(f"Iniciando entrenamiento paralelo de {len(activos_lista)} cerebros...")
    
    with ProcessPoolExecutor() as executor:
        resultados = list(executor.map(tarea_entrenamiento, activos_lista))
    
    for symbol, modelo, status in resultados:
        if modelo: MODELOS_IA[symbol] = modelo
        else: agregar_log(f"Fallo IA {symbol}: {status}")

def seleccionar_mejores_activos_dinamico():
    """Selecciona los activos más prometedores con manejo de errores"""
    agregar_log("Escaneando mercado...")
    
    # Intentar obtener los símbolos (reintentar si devuelve None)
    todos_simbolos = None
    for i in range(5): # 5 intentos
        todos_simbolos = mt5.symbols_get()
        if todos_simbolos is not None:
            break
        time.sleep(1)

    if todos_simbolos is None:
        agregar_log("❌ ERROR: No se pudo obtener la lista de símbolos de MT5. ¿Está abierto el terminal?")
        return []

    candidatos_raw = []
    for s in todos_simbolos:
        # Filtro de visibilidad y relevancia
        if s.visible and any(x in s.name for x in ["USD", "BTC", "XAU", "NAS", "ETH", "GOLD"]):
            # Filtro por spread y precio
            spread_val = s.spread if s.spread > 0 else 1000
            ask_val = s.ask if s.ask > 0 else 1
            score = (spread_val / ask_val) * 1000 
            candidatos_raw.append({"symbol": s.name, "score": score})

    if not candidatos_raw:
        agregar_log("⚠️ No se encontraron activos candidatos. Revisa 'Observación de Mercado'.")
        return []

    seleccionados = sorted(candidatos_raw, key=lambda x: x['score'])[:MAX_ACTIVOS]
    return [s['symbol'] for s in seleccionados]

# ==========================================
# 3. TELEMETRÍA Y EJECUCIÓN
# ==========================================

def update_db_async(symbol, last, prob, estado, acc):
    try:
        db.actualizar_estado_bot(True, acc.balance, acc.equity)
        db.sincronizar_trades(MAGIC_NUMBER) # Siempre sincronizamos en cada ciclo
        db.actualizar_monitoreo(symbol, float(last['close']), float(last['rsi']), float(prob), estado)
    except:
        pass

def abrir_orden(tipo, symbol, atr):
    try:
        acc = mt5.account_info()
        if acc.margin_free < (acc.balance * 0.05): # Margen libre > 5% del balance
            agregar_log(f"Margen bajo en {symbol}. Orden omitida.")
            return

        lotaje = 0.01 if any(x in symbol for x in ["BTC", "XAU", "ETH", "NAS", "US30", "GOLD"]) else 0.1
        
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
            agregar_log(f"¡ENTRADA EXITOSA! {tipo} {symbol}")
        else:
            agregar_log(f"FALLO {symbol}: {res.comment} (Code: {res.retcode})")
    except Exception as e:
        agregar_log(f"Error Ejecución: {e}")

# ==========================================
# 4. LOOP PRINCIPAL "EYE OF PROVIDENCE"
# ==========================================

if __name__ == "__main__":
    # Inicializar con reintentos
    if not mt5.initialize():
        print(f"Error inicializando MT5: {mt5.last_error()}")
        quit()
        
    print("✅ MT5 Conectado. Iniciando escaneo de activos...")
    
    activos_actuales = seleccionar_mejores_activos_dinamico()
    
    if not activos_actuales:
        print("❌ El bot no pudo seleccionar activos. Deteniendo.")
        mt5.shutdown()
        quit()
        
    inicializar_cerebros_paralelos(activos_actuales)
    
    db_executor = ThreadPoolExecutor(max_workers=2)
    ultima_reseleccion = datetime.now()

    while True:
        try:
            # Re-selección dinámica de activos
            if datetime.now() > ultima_reseleccion + timedelta(hours=RE_SCAN_HOURS):
                activos_actuales = seleccionar_mejores_activos_dinamico()
                # Re-entrenar solo los modelos que no teníamos o son nuevos
                for s in activos_actuales:
                    if s not in MODELOS_IA:
                        modelo_nuevo, status_mod = cargar_o_evolucionar(s)
                        MODELOS_IA[s] = modelo_nuevo
                        agregar_log(f"Nuevo activo {s} añadido. Cerebro {status_mod}")
                ultima_reseleccion = datetime.now()
            
            acc = mt5.account_info()
            posiciones = mt5.positions_get(magic=MAGIC_NUMBER)
            num_pos = len(posiciones) if posiciones else 0
            dashboard = []

            for s in activos_actuales:
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
                
                # --- PREDICCIÓN IA ---
                prob = 0.5
                if MODELOS_IA.get(s):
                    input_ia = pd.DataFrame([last[FEATURES].values], columns=FEATURES)
                    prob = MODELOS_IA[s].predict_proba(input_ia)[0][1]
                
                # --- LÓGICA DE SEÑAL VERBOSE ---
                señal = "ESPERAR"
                verbose_razon = "Sin Señal"
                
                # Filtros de entrada
                atr_avg = df['atr'].tail(20).mean()
                distancia_ema = abs(last['close'] - last['ema_l']) / last['close']
                
                mercado_activo = last['atr'] > (atr_avg * 0.7)
                ema_ok_compra = last['close'] > last['ema_l']
                ema_ok_venta = last['close'] < last['ema_l']
                rsi_ok_compra = last['rsi'] > 48
                rsi_ok_venta = last['rsi'] < 52
                
                if not mercado_activo:
                    verbose_razon = "Baja Volatilidad"
                elif not ema_ok_compra and not ema_ok_venta:
                    verbose_razon = "Rango Lateral (EMA)"
                elif prob < PROBABILIDAD_IA_MINIMA and prob > (1-PROBABILIDAD_IA_MINIMA):
                    verbose_razon = f"IA Neutral ({prob:.2%})"
                
                # Decisión Final
                if mercado_activo and ema_ok_compra and rsi_ok_compra and prob > PROBABILIDAD_IA_MINIMA:
                    señal = "COMPRA"
                    verbose_razon = "Confluencia COMPRA"
                elif mercado_activo and ema_ok_venta and rsi_ok_venta and prob < (1 - PROBABILIDAD_IA_MINIMA):
                    señal = "VENTA"
                    verbose_razon = "Confluencia VENTA"
                
                abierta = any(p.symbol == s for p in posiciones) if posiciones else False
                estado_web = "ABIERTA" if abierta else señal

                # Ejecutar Trades
                if señal != "ESPERAR" and not abierta and num_pos < MAX_POSICIONES_GLOBALES:
                    abrir_orden(señal, s, last['atr'])
                    num_pos += 1
                
                # Telemetría Asíncrona
                db_executor.submit(update_db_async, s, last, prob, estado_web, acc)
                
                dashboard.append({"s": s, "p": last['close'], "ia": prob, "st": estado_web, "m": verbose_razon})

            # Dashboard Local de Consola
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"--- SENTINEL v6.0 Eye of Providence | {datetime.now().strftime('%H:%M:%S')} ---")
            print(f"Equity: {acc.equity:.2f} | Posiciones: {num_pos}/{MAX_POSICIONES_GLOBALES} | IA Threshold: {PROBABILIDAD_IA_MINIMA}")
            print("-" * 100)
            print(f"{'ACTIVO':<12} | {'PRECIO':<10} | {'IA PROB':<10} | {'ESTADO':<10} | {'RAZÓN/ACCIÓN':<30}")
            print("-" * 100)
            for d in dashboard[:MAX_ACTIVOS]: # Mostrar solo los activos seleccionados
                print(f"{d['s']:<12} | {d['p']:<10.4f} | {d['ia']:.2%} | {d['st']:<10} | {d['m']:<30}")
            print("-" * 100)
            print(" ÚLTIMOS LOGS DE SISTEMA:")
            for l in reversed(LOG_BUFFER): print(f"> {l}")
            
            time.sleep(15) # Ciclo optimizado cada 15 segundos

        except Exception as e:
            db_executor.submit(db.actualizar_estado_bot, False, 0, 0)
            print(f"Error Crítico en Loop: {e}")
            time.sleep(10)