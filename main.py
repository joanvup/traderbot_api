from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import uvicorn
import csv
from fastapi.responses import StreamingResponse
import io


# Configuración
SECRET_KEY = "SUPER_SECRET_KEY_CAMBIAME_123" # En prod usar variable de entorno
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 1 día

# Conexión MySQL (Ajusta tus credenciales)
# Formato: mysql+mysqlconnector://user:password@host/dbname
SQLALCHEMY_DATABASE_URL = "mysql+mysqlconnector://user_bot:S0portefcbv@localhost/traderbot_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI(title="TraderBot API")

# Habilitar CORS para el Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción poner tu dominio
    allow_methods=["*"],
    allow_headers=["*"],
)

# Funciones de utilidad
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password(plain_password, hashed_password):
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        print(f"Error en verificación: {e}")
        return False

# --- RUTAS ---

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    db = SessionLocal()
    print(f"🔍 Intentando login para usuario: {form_data.username}") # Log de consola
    
    result = db.execute(
        text("SELECT password_hash FROM users WHERE username = :u"), 
        {"u": form_data.username}
    ).fetchone()
    db.close()
    
    if not result:
        print("❌ Usuario no encontrado en la base de datos")
        raise HTTPException(status_code=400, detail="Usuario no encontrado")
    
    # Verificación
    password_valida = verify_password(form_data.password, result[0])
    
    if not password_valida:
        print("❌ Contraseña incorrecta")
        raise HTTPException(status_code=400, detail="Contraseña incorrecta")
    
    print("✅ Login exitoso")
    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/stats/summary")
async def get_summary(token: str = Depends(oauth2_scheme)):
    db = SessionLocal()
    # Contar posiciones reales en la tabla live_positions
    count_live = db.execute(text("SELECT COUNT(*) FROM live_positions")).scalar() or 0
    # Solo contamos trades reales (no el depósito) para el Win Rate
    q_trades = text("""
        SELECT 
            SUM(profit) as total_profit,
            COUNT(*) as total_trades,
            COUNT(CASE WHEN profit > 0 THEN 1 END) as wins
        FROM trades WHERE symbol != 'BALANCE'
    """)
    res = db.execute(q_trades).fetchone()
    
    # El profit total sí debe incluir todo para cuadrar con el balance
    q_net = text("SELECT SUM(profit) FROM trades")
    net_profit_all = db.execute(q_net).scalar() or 0

    status_res = db.execute(text("SELECT balance, equity, is_active FROM bot_status WHERE id=1")).fetchone()
    db.close()

    total_trades = res[1] if res[1] else 0
    win_rate = (res[2] / total_trades * 100) if total_trades > 0 else 0

    return {
        "total_profit": round(float(net_profit_all), 2),
        "win_rate": round(win_rate, 2),
        "total_trades": total_trades,
        "current_balance": float(status_res[0]) if status_res else 0,
        "current_equity": float(status_res[1]) if status_res else 0,
        "is_active": status_res[2] if status_res else False,
        "open_positions": count_live, # Usaremos este valor para la tarjeta KPI
    }

@app.get("/stats/trades")
async def get_paginated_trades(page: int = 1, limit: int = 10, token: str = Depends(oauth2_scheme)):
    db = SessionLocal()
    try:
        offset = (page - 1) * limit
        
        # Agregamos un try-except interno para capturar el error exacto de SQL
        query = text("""
            SELECT 
                id, ticket, symbol, type, lotage, open_price, open_time, close_price, profit, close_time, magic_number
            FROM trades 
            ORDER BY close_time DESC 
            LIMIT :limit OFFSET :offset
        """)
        
        res = db.execute(query, {"limit": limit, "offset": offset}).fetchall()

        total_trades = db.execute(text("SELECT COUNT(*) FROM trades")).scalar()
        
        trades_data = []
        for r in res:
            trades_data.append({
                "id": r[0], 
                "ticket": r[1],
                "symbol": r[2], 
                "type": r[3],
                "lotage": float(r[4]),
                "open_price": float(r[5]),
                # Verificación de seguridad para fechas nulas
                "open_time": r[6].strftime("%Y-%m-%d %H:%M:%S") if r[6] else "N/A", 
                "close_price": float(r[7]),
                "profit": float(r[8]), 
                "close_time": r[9].strftime("%Y-%m-%d %H:%M:%S") if r[9] else "N/A",
                "magic_number": r[10]
            })
        return {"trades": trades_data, "total_trades": total_trades, "current_page": page, "page_size": limit}
    
    except Exception as e:
        print(f"ERROR SQL en trades: {str(e)}") # Esto saldrá en journalctl
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    finally:
        db.close()


@app.get("/stats/history")
async def get_history(token: str = Depends(oauth2_scheme)):
    db = SessionLocal()
    # Traemos todo, incluyendo el depósito
    query = text("SELECT close_time, profit, type FROM trades ORDER BY close_time ASC")
    res = db.execute(query).fetchall()
    db.close()
    
    history = []
    balance_acumulado = 0
    
    for r in res:
        balance_acumulado += float(r[1])
        history.append({
            "time": r[0].strftime("%d/%m %H:%M"),
            "balance": round(balance_acumulado, 2)
        })
    
    return history
    
@app.get("/stats/monitoring")
async def get_monitoring(token: str = Depends(oauth2_scheme)):
    db = SessionLocal()
    res = db.execute(text("SELECT * FROM market_monitoring ORDER BY symbol ASC")).fetchall()
    db.close()
    return [{"symbol": r.symbol, "price": float(r.price), "rsi": float(r.rsi), 
             "ia_prob": float(r.ia_prob), "status": r.status} for r in res]

@app.get("/export/csv")
async def export_trades_csv(token: str = Depends(oauth2_scheme)):
    db = SessionLocal()
    query = text("SELECT symbol, type, lotage, open_price, close_price, profit, close_time FROM trades ORDER BY close_time DESC")
    res = db.execute(query).fetchall()
    db.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Symbol", "Type", "Lotage", "Open Price", "Close Price", "Profit", "Close Time"])
    
    for r in res:
        writer.writerow([r[0], r[1], r[2], float(r[3]), float(r[4]), float(r[5]), r[6].strftime("%Y-%m-%d %H:%M")])
    
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=traderbot_report.csv"}
    )

@app.get("/stats/active-trades")
async def get_active_trades(token: str = Depends(oauth2_scheme)):
    db = SessionLocal()
    res = db.execute(text("SELECT * FROM live_positions ORDER BY time_open DESC")).fetchall()
    db.close()
    
    return [{
        "ticket": r.ticket, "symbol": r.symbol, "type": r.type, "lotage": float(r.lotage),
        "price_open": float(r.price_open), "price_current": float(r.price_current),
        "sl": float(r.sl), "tp": float(r.tp), "profit": float(r.profit),
        "time_open": r.time_open.strftime("%H:%M:%S")
    } for r in res]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)