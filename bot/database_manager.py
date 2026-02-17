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
        import MetaTrader5 as mt5
        from datetime import datetime, timedelta
        
        # 30 días de historial
        from_date = datetime.now() - timedelta(days=30)
        history_deals = mt5.history_deals_get(from_date, datetime.now(), group=f"*{magic_number}*")
        
        if history_deals:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                for deal in history_deals:
                    # FILTRO: Solo trades reales (no depósitos) y que sean cierres (entry out=1)
                    if deal.symbol != "" and deal.entry == 1:
                        query = """
                            INSERT IGNORE INTO trades 
                            (ticket, symbol, type, lotage, open_price, close_price, profit, close_time, magic_number)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        t_type = "BUY" if deal.type == 1 else "SELL"
                        c_time = datetime.fromtimestamp(deal.time)
                        # En MT5, el beneficio real ya incluye swaps y comisiones
                        cursor.execute(query, (
                            deal.ticket, deal.symbol, t_type, deal.volume,
                            deal.price - (deal.profit/deal.volume/10) if deal.volume > 0 else 0,
                            deal.price, deal.profit, c_time, magic_number
                        ))
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as e:
                print(f"Error DB: {e}")

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