import mysql.connector
from datetime import datetime, timedelta # Agregamos timedelta aquí
import MetaTrader5 as mt5


class DatabaseManager:
    def __init__(self, host, user, password, database):
        self.config = {
            'host': host,
            'user': user,
            'password': password,
            'database': database,
            'connect_timeout': 5 # Tiempo de espera para no bloquear el bot
        }

    def _get_connection(self):
        return mysql.connector.connect(**self.config)

    def actualizar_estado_bot(self, is_active, balance, equity):
        """Actualiza el 'latido' del bot y sus métricas financieras"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            query = """
                INSERT INTO bot_status (id, last_ping, is_active, balance, equity)
                VALUES (1, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                last_ping=%s, is_active=%s, balance=%s, equity=%s
            """
            now = datetime.now()
            values = (now, is_active, balance, equity, now, is_active, balance, equity)
            cursor.execute(query, values)
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error DB (Status): {e}")

    def sincronizar_trades(self, magic_number):
        # Buscamos desde el inicio de los tiempos para recuperar todo
        from_date = datetime(2020, 1, 1)
        to_date = datetime.now()
        
        # 1. Obtenemos TODOS los deals (sin filtrar por Magic Number por ahora)
        history_deals = mt5.history_deals_get(from_date, to_date)
        
        if history_deals is None:
            print(f"Error MT5 Historial: {mt5.last_error()}")
            return

        deals_procesados = 0
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            for deal in history_deals:
                # Procesamos solo trades que tengan impacto financiero (profit != 0)
                if deal.profit != 0: 
                    query = """
                        INSERT IGNORE INTO trades 
                        (ticket, symbol, type, lotage, open_price, close_price, profit, close_time, magic_number)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    # 0=Buy, 1=Sell (En MT5 Deals)
                    t_type = "BUY" if deal.type == 0 else "SELL"
                    c_time = datetime.fromtimestamp(deal.time)
                    
                    # Intentamos capturar el magic_number real del deal
                    m_num = deal.magic if deal.magic != 0 else magic_number
                    
                    values = (
                        deal.ticket, deal.symbol, t_type, deal.volume,
                        deal.price, deal.price, deal.profit, # Usamos price como ref
                        c_time, m_num
                    )
                    cursor.execute(query, values)
                    deals_procesados += 1
            
            conn.commit()
            cursor.close()
            conn.close()
            if deals_procesados > 0:
                print(f"✅ Sincronizados {deals_procesados} trades con MySQL.")
        except Exception as e:
            print(f"❌ Error Crítico DB Trades: {e}")

    def actualizar_monitoreo(self, symbol, price, rsi, ia_prob, status):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            query = """
                INSERT INTO market_monitoring (symbol, price, rsi, ia_prob, status)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                price=%s, rsi=%s, ia_prob=%s, status=%s
            """
            cursor.execute(query, (symbol, price, rsi, ia_prob, status, price, rsi, ia_prob, status))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error DB (Monitoreo): {e}")