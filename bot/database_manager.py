import mysql.connector
from datetime import datetime, timedelta

class DatabaseManager:
    def __init__(self, host, user, password, database):
        self.config = {
            'host': host,
            'user': user,
            'password': password,
            'database': database,
            'connect_timeout': 10 # Aumentado el timeout para conexiones remotas
        }

    def _get_connection(self):
        return mysql.connector.connect(**self.config)

    def actualizar_estado_bot(self, is_active, balance, equity):
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
        """
        Sincroniza trades buscando en el historial de POSICIONES CERRADAS de MT5.
        Esto es más preciso para obtener open_time y open_price.
        """
        import MetaTrader5 as mt5
        
        # Buscamos historial desde el inicio del 2020 para capturar todo
        from_date = datetime(2020, 1, 1) 
        to_date = datetime.now()
        
        # Obtenemos TODAS las posiciones cerradas del historial de la cuenta
        closed_positions = mt5.history_positions_get(from_date, to_date)

        if closed_positions is None:
            print(f"Error MT5: No se pudo obtener historial de posiciones. {mt5.last_error()}")
            return

        procesados = 0
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            for pos in closed_positions:
                # Solo procesamos posiciones cerradas que tengan un profit != 0 y sean de nuestro bot
                if pos.profit != 0 and pos.magic == magic_number: 
                    # Verificar si ya existe este ticket en la DB para evitar duplicados
                    cursor.execute(f"SELECT COUNT(*) FROM trades WHERE ticket = {pos.ticket}")
                    if cursor.fetchone()[0] > 0:
                        continue # Ya existe, saltar

                    # Determinar el tipo de operación (Buy/Sell)
                    trade_type = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                    
                    query = """
                        INSERT IGNORE INTO trades 
                        (ticket, symbol, type, lotage, open_price, open_time, close_price, profit, close_time, magic_number)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    values = (
                        pos.ticket,
                        pos.symbol,
                        trade_type,
                        pos.volume,
                        pos.price_open,
                        datetime.fromtimestamp(pos.time),      # open_time de la posición
                        pos.price_close,
                        pos.profit,
                        datetime.fromtimestamp(pos.time_update), # close_time (actualización final)
                        pos.magic
                    )
                    cursor.execute(query, values)
                    procesados += 1
            
            conn.commit()
            cursor.close()
            conn.close()
            if procesados > 0:
                print(f"✅ Sincronizados {procesados} trades con MySQL desde posiciones.")
        except Exception as e:
            print(f"❌ Error Crítico DB Posiciones: {e}")