from passlib.context import CryptContext
from sqlalchemy import create_engine, text

# Configura tu conexión igual que en main.py
DB_URL = "mysql+mysqlconnector://user_bot:S0portefcbv@localhost/traderbot_db"
engine = create_engine(DB_URL)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def reset_admin():
    password_plana = "admin123"
    nuevo_hash = pwd_context.hash(password_plana)
    
    with engine.connect() as conn:
        # Limpiamos y creamos el usuario
        conn.execute(text("DELETE FROM users WHERE username = 'admin'"))
        conn.execute(text("INSERT INTO users (username, password_hash) VALUES (:u, :p)"), 
                     {"u": "admin", "p": nuevo_hash})
        conn.commit()
    print(f"✅ Usuario 'admin' reseteado con éxito.")
    print(f"🔑 Contraseña: {password_plana}")

if __name__ == "__main__":
    reset_admin()