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
        from datetime import datetime

        # 1. Rango total desde el inicio
        from_date = datetime(2010, 1, 1) 
        to_date = datetime.now()
        
        # 2. Obtenemos DEALS (transacciones contables)
        history_deals = mt5.history_deals_get(from_date, to_date)

        if history_deals is None:
            print(f"Error MT5: {mt5.last_error()}")
            return

        procesados = 0
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            for deal in history_deals:
                # --- FILTRO DE INTEGRIDAD ---
                # Procesamos si es:
                # A. Un cierre de operación (entry == 1)
                # B. El depósito inicial (type == 2 -> DEAL_TYPE_BALANCE)
                is_balance = deal.type == 2 
                is_close = deal.entry == 1

                if is_balance or is_close:
                    # Verificar si ya existe este ticket
                    cursor.execute(f"SELECT id FROM trades WHERE ticket = {deal.ticket}")
                    if cursor.fetchone(): continue

                    # Valores por defecto para depósitos
                    symbol = deal.symbol if deal.symbol != "" else "BALANCE"
                    trade_type = "DEPOSIT" if is_balance else ("SELL" if deal.type == 0 else "BUY")
                    c_time = datetime.fromtimestamp(deal.time)
                    open_time = c_time
                    open_price = deal.price

                    # Si es un cierre, intentamos buscar su apertura para tener tiempos exactos
                    if is_close:
                        entry_deals = mt5.history_deals_get(position=deal.position_id)
                        if entry_deals:
                            for d_entry in entry_deals:
                                if d_entry.entry == 0: # IN
                                    open_time = datetime.fromtimestamp(d_entry.time)
                                    open_price = d_entry.price
                                    break

                    query = """
                        INSERT INTO trades 
                        (ticket, symbol, type, lotage, open_price, open_time, close_price, profit, close_time, magic_number)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    
                    # Profit neto incluyendo comisiones y swaps
                    net_profit = deal.profit + deal.commission + deal.swap

                    values = (
                        deal.ticket, symbol, trade_type, deal.volume,
                        open_price, open_time, deal.price,
                        net_profit, c_time, deal.magic
                    )
                    cursor.execute(query, values)
                    procesados += 1
            
            conn.commit()
            cursor.close()
            conn.close()
            if procesados > 0:
                print(f"✅ Sincronización Exitosa: {procesados} registros nuevos (incluyendo balance).")
        except Exception as e:
            print(f"❌ Error en Sincronización: {e}")