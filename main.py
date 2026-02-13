from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import uvicorn



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
    # Query para obtener Profit Total y Win Rate
    query = text("""
        SELECT 
            SUM(profit) as total_profit,
            COUNT(*) as total_trades,
            COUNT(CASE WHEN profit > 0 THEN 1 END) as wins
        FROM trades
    """)
    res = db.execute(query).fetchone()
    
    # Query para balance actual
    status_res = db.execute(text("SELECT balance, equity, is_active FROM bot_status WHERE id=1")).fetchone()
    db.close()

    total_trades = res[1] if res[1] else 0
    win_rate = (res[2] / total_trades * 100) if total_trades > 0 else 0

    return {
        "total_profit": float(res[0]) if res[0] else 0,
        "win_rate": round(win_rate, 2),
        "total_trades": total_trades,
        "current_balance": float(status_res[0]) if status_res else 0,
        "is_active": status_res[2] if status_res else False
    }
# Añadir al final de main.py (dentro de las rutas protegidas)

@app.get("/stats/trades")
async def get_recent_trades(token: str = Depends(oauth2_scheme)):
    db = SessionLocal()
    query = text("SELECT * FROM trades ORDER BY close_time DESC LIMIT 10")
    res = db.execute(query).fetchall()
    db.close()
    
    # Convertir resultados a lista de diccionarios
    trades = []
    for r in res:
        trades.append({
            "id": r.id, "symbol": r.symbol, "type": r.type,
            "profit": float(r.profit), "close_time": r.close_time.strftime("%Y-%m-%d %H:%M")
        })
    return trades

@app.get("/stats/history")
async def get_history(token: str = Depends(oauth2_scheme)):
    db = SessionLocal()
    # Generamos una curva de balance acumulado
    query = text("SELECT close_time, profit FROM trades ORDER BY close_time ASC")
    res = db.execute(query).fetchall()
    db.close()
    
    history = []
    balance_acumulado = 100000.0 # Balance inicial base
    for r in res:
        balance_acumulado += float(r.profit)
        history.append({
            "time": r.close_time.strftime("%d/%m"),
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)