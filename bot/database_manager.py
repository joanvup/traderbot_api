import mysql.connector
from datetime import datetime, timedelta

class DatabaseManager:
    def __init__(self, host, user, password, database):
        self.config = {
            'host': host, 'user': user, 'password': password,
            'database': database, 'connect_timeout': 10
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
                ON DUPLICATE KEY UPDATE last_ping=%s, is_active=%s, balance=%s, equity=%s
            """
            now = datetime.now()
            cursor.execute(query, (now, is_active, balance, equity, now, is_active, balance, equity))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e: print(f"Error DB Status: {e}")

    def sincronizar_trades(self, magic_number):
        """Módulo de Autocuración: Sincroniza historial completo MT5 vs MySQL"""
        import MetaTrader5 as mt5
        from_date = datetime(2024, 1, 1) # Desde el inicio del despliegue
        history_deals = mt5.history_deals_get(from_date, datetime.now()+timedelta(days=1))
        
        if not history_deals: return

        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT ticket FROM trades")
            db_tickets = {row[0] for row in cursor.fetchall()}
            
            nuevos = 0
            for d in history_deals:
                if d.ticket not in db_tickets:
                    is_balance = d.type == 2
                    is_close = d.entry == 1
                    if is_balance or is_close:
                        sym = d.symbol if d.symbol != "" else "BALANCE"
                        t_type = "DEPOSIT" if is_balance else ("SELL" if d.type == 0 else "BUY")
                        c_time = datetime.fromtimestamp(d.time)
                        
                        # Buscar apertura real para trades cerrados
                        o_time, o_price = c_time, d.price
                        if is_close:
                            entry_deals = mt5.history_deals_get(position=d.position_id)
                            if entry_deals:
                                for ed in entry_deals:
                                    if ed.entry == 0:
                                        o_time, o_price = datetime.fromtimestamp(ed.time), ed.price
                                        break

                        query = """INSERT INTO trades (ticket, symbol, type, lotage, open_price, open_time, close_price, profit, close_time, magic_number)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                        cursor.execute(query, (d.ticket, sym, t_type, d.volume, o_price, o_time, d.price, (d.profit + d.commission + d.swap), c_time, d.magic))
                        nuevos += 1
            conn.commit()
            if nuevos > 0: print(f"✅ Autocuración: {nuevos} registros recuperados.")
            cursor.close()
            conn.close()
        except Exception as e: print(f"Error Sincro: {e}")

    def actualizar_posiciones_vivas(self, posiciones, magic_number):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM live_positions") # Limpieza atómica
            if posiciones:
                query = """INSERT INTO live_positions (ticket, symbol, type, lotage, price_open, price_current, sl, tp, profit, time_open)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                for p in posiciones:
                    if p.magic == magic_number:
                        cursor.execute(query, (p.ticket, p.symbol, ("BUY" if p.type==0 else "SELL"), p.volume, p.price_open, p.price_current, p.sl, p.tp, p.profit, datetime.fromtimestamp(p.time)))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e: print(f"Error Live Positions: {e}")

    def actualizar_monitoreo(self, symbol, price, rsi, ia_prob, status):
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            query = """INSERT INTO market_monitoring (symbol, price, rsi, ia_prob, status) VALUES (%s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE price=%s, rsi=%s, ia_prob=%s, status=%s"""
            cursor.execute(query, (symbol, price, rsi, ia_prob, status, price, rsi, ia_prob, status))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e: print(f"Error Monitoreo: {e}")