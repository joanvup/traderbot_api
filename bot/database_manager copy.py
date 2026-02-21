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
        """Módulo de Autocuración: Compara MT5 vs MySQL y recupera trades perdidos"""
        import MetaTrader5 as mt5
        from datetime import datetime, timedelta
        
        # 1. Definimos un rango amplio (desde el inicio del año para seguridad)
        from_date = datetime(2024, 1, 1)
        to_date = datetime.now() + timedelta(days=1) # Sumamos un día extra para asegurar
        
        # 2. Obtenemos TODOS los 'Deals' (transacciones reales) de la cuenta
        # No filtramos por magic_number aquí para poder detectar TODO lo que afectó el balance
        history_deals = mt5.history_deals_get(from_date, to_date)
        
        if history_deals is None or len(history_deals) == 0:
            return

        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 3. Obtenemos los tickets que ya tenemos en MySQL para no re-procesar
            cursor.execute("SELECT ticket FROM trades")
            tickets_en_db = {row[0] for row in cursor.fetchall()}
            
            nuevos_registros = 0
            for deal in history_deals:
                # Si el ticket no está en nuestra DB y es un cierre o un depósito
                if deal.ticket not in tickets_en_db:
                    # Solo procesamos cierres (entry=1) o balance inicial (type=2)
                    is_balance = deal.type == 2
                    is_close = deal.entry == 1
                    
                    if is_balance or is_close:
                        symbol = deal.symbol if deal.symbol != "" else "BALANCE"
                        trade_type = "DEPOSIT" if is_balance else ("SELL" if deal.type == 0 else "BUY")
                        c_time = datetime.fromtimestamp(deal.time)
                        
                        # Intentamos buscar la apertura para tener el open_time exacto
                        open_time = c_time
                        open_price = deal.price
                        if is_close:
                            entry_deals = mt5.history_deals_get(position=deal.position_id)
                            if entry_deals:
                                for d_entry in entry_deals:
                                    if d_entry.entry == 0:
                                        open_time = datetime.fromtimestamp(d_entry.time)
                                        open_price = d_entry.price
                                        break

                        query = """
                            INSERT INTO trades 
                            (ticket, symbol, type, lotage, open_price, open_time, close_price, profit, close_time, magic_number)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        # Sumamos profit + comisiones + swaps para tener el dinero NETO real
                        net_profit = deal.profit + deal.commission + deal.swap
                        
                        values = (
                            deal.ticket, symbol, trade_type, deal.volume,
                            open_price, open_time, deal.price,
                            net_profit, c_time, deal.magic
                        )
                        cursor.execute(query, values)
                        nuevos_registros += 1

            conn.commit()
            if nuevos_registros > 0:
                print(f"✅ Autocuración completada: Se recuperaron {nuevos_registros} trades perdidos.")
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"❌ Error en el módulo de autocuración: {e}")
    
    def actualizar_posiciones_vivas(self, posiciones_mt5, magic_number):
        """Sincroniza posiciones filtrando estrictamente por Magic Number"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 1. Limpiar la tabla COMPLETAMENTE antes de insertar lo nuevo
            cursor.execute("DELETE FROM live_positions")
            
            if posiciones_mt5:
                query = """
                    INSERT INTO live_positions 
                    (ticket, symbol, type, lotage, price_open, price_current, sl, tp, profit, time_open)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                for p in posiciones_mt5:
                    # FILTRO CRÍTICO: Solo lo que pertenece a este bot
                    if p.magic == magic_number:
                        t_type = "BUY" if p.type == 0 else "SELL"
                        values = (
                            p.ticket, p.symbol, t_type, p.volume,
                            p.price_open, p.price_current, p.sl, p.tp, p.profit,
                            datetime.fromtimestamp(p.time)
                        )
                        cursor.execute(query, values)
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error DB (Live Positions Fix): {e}")