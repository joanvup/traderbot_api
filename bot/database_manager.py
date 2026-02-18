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
        import MetaTrader5 as mt5
        from datetime import datetime, timedelta

        # 1. Forzamos la fecha desde el inicio de la cuenta (o un año muy atrás)
        from_date = datetime(2010, 1, 1) 
        to_date = datetime.now()
        
        # 2. Obtenemos DEALS (transacciones individuales). Es más fiable que 'positions'
        # Pedimos TODOS los deals de la cuenta
        history_deals = mt5.history_deals_get(from_date, to_date)

        if history_deals is None:
            print(f"Error MT5: {mt5.last_error()}")
            return

        procesados = 0
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            for deal in history_deals:
                # Filtro 1: Solo trades de CIERRE (entry == 1 es OUT)
                # Filtro 2: Ignorar depósitos (symbol no debe estar vacío)
                if deal.entry == 1 and deal.symbol != "":
                    
                    # Buscamos si el ticket ya existe
                    cursor.execute(f"SELECT id FROM trades WHERE ticket = {deal.ticket}")
                    if cursor.fetchone(): continue

                    # Obtenemos el tipo original
                    # deal.type: 0 es Buy (el cierre de un sell), 1 es Sell (el cierre de un buy)
                    trade_type = "SELL" if deal.type == 0 else "BUY"
                    
                    # IMPORTANTE: Para obtener el OPEN_TIME real en un deal de cierre, 
                    # MetaTrader vincula el deal con la posición.
                    close_time = datetime.fromtimestamp(deal.time)
                    
                    # Intentamos buscar el momento de apertura (el deal de entrada)
                    # Si no lo encontramos, usamos una estimación o el mismo tiempo
                    open_time = close_time # Valor por defecto
                    open_price = deal.price # Valor por defecto

                    # Buscamos la transacción de entrada (IN) para esta misma posición
                    entry_deals = mt5.history_deals_get(position=deal.position_id)
                    if entry_deals:
                        for d_entry in entry_deals:
                            if d_entry.entry == 0: # 0 es IN (Apertura)
                                open_time = datetime.fromtimestamp(d_entry.time)
                                open_price = d_entry.price
                                break

                    query = """
                        INSERT INTO trades 
                        (ticket, symbol, type, lotage, open_price, open_time, close_price, profit, close_time, magic_number)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    values = (
                        deal.ticket,
                        deal.symbol,
                        trade_type,
                        deal.volume,
                        open_price,
                        open_time,
                        deal.price,
                        deal.profit + deal.commission + deal.swap, # Profit Neto Real
                        close_time,
                        deal.magic
                    )
                    cursor.execute(query, values)
                    procesados += 1
            
            conn.commit()
            cursor.close()
            conn.close()
            if procesados > 0:
                print(f"✅ Sincronización Masiva: {procesados} trades nuevos guardados.")
        except Exception as e:
            print(f"❌ Error en Sincronización Masiva: {e}")