import mysql.connector
from datetime import datetime, timedelta # Agregamos timedelta aquí

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
        """Busca trades cerrados en MT5 y los guarda en MySQL si no existen"""
        import MetaTrader5 as mt5
        
        # CORRECCIÓN: Usamos timedelta directamente
        from_date = datetime.now() - timedelta(days=7)
        
        # Obtener historial desde MT5
        history_deals = mt5.history_deals_get(from_date, datetime.now(), group=f"*{magic_number}*")
        
        if history_deals and len(history_deals) > 0:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                for deal in history_deals:
                    # Entry 1 significa 'OUT' (posición cerrada)
                    if deal.entry == 1: 
                        query = """
                            INSERT IGNORE INTO trades 
                            (ticket, symbol, type, lotage, open_price, close_price, profit, close_time, magic_number)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        # Determinar tipo de operación
                        # deal.type 0=Buy, 1=Sell. Si el deal es OUT y era Buy, el tipo original es BUY.
                        t_type = "BUY" if deal.type == 1 else "SELL"
                        
                        c_time = datetime.fromtimestamp(deal.time)
                        
                        # Calculamos un precio de apertura estimado para la DB
                        # (Opcional: podrías buscar el deal.entry == 0 para el precio exacto)
                        values = (
                            deal.ticket, deal.symbol, t_type, deal.volume,
                            deal.price, # precio de cierre
                            deal.price, # precio de cierre
                            deal.profit, c_time, magic_number
                        )
                        cursor.execute(query, values)
                
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as e:
                print(f"Error DB (Trades): {e}")