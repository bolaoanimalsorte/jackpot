from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import random
import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi.staticfiles import StaticFiles
import uvicorn



app.mount("/", StaticFiles(directory="static", html=True), name="static")
# Configurar o banco de dados SQLite
DATABASE_URL = "sqlite:///jackpot.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Criar sessão com o banco de dados
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Criar a base para o SQLAlchemy
Base = declarative_base()

# Modelo do Banco de Dados
class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    last_access = Column(DateTime, default=datetime.datetime.utcnow)
    attempts = Column(Integer, default=5)

# Criar tabelas no banco
Base.metadata.create_all(engine)

# Inicializar FastAPI
app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelo Pydantic para o corpo da requisição /play/
class PlayRequest(BaseModel):
    email: str

# Função para obter a sessão do banco
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Função para enviar email ao administrador se o jogador ganhar usando SMTP

def send_email_winner(email):
    sender_email = os.environ.get("GMAIL_EMAIL", "bolaoanimal@gmail.com")  # Pega do ambiente
    sender_password = os.environ.get("GMAIL_APP_PASSWORD", "peuc kvmf qdum dgmh")  # Pega do ambiente
    receiver_email = "bolaoanimal@gmail.com"

    subject = "\U0001F389 Jackpot Ganhador!"
    body = f"O jogador {email} ganhou o jackpot em {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}!"

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        print("Email enviado com sucesso!")
    except smtplib.SMTPAuthenticationError:
        print("Erro de autenticação! Verifique seu e-mail e senha de aplicativo.")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

# Função para resetar tentativas se for um novo dia
def reset_attempts_if_new_day(player, db):
    now = datetime.datetime.utcnow()
    last = player.last_access
    if now.date() > last.date():
        player.attempts = 5
        player.last_access = now
        db.commit()

# Endpoint para iniciar o jogo
@app.post("/play/")
def play(request: PlayRequest, db: Session = Depends(get_db)):
    email = request.email
    player = db.query(Player).filter_by(email=email).first()

    if not player:
        player = Player(email=email, attempts=5, last_access=datetime.datetime.utcnow())
        db.add(player)
        db.commit()
    else:
        reset_attempts_if_new_day(player, db)

    if player.attempts <= 0:
        return {"message": "Você já usou todas as suas tentativas hoje!", "attemptsLeft": 0}

    numbers = [random.randint(1, 5) for _ in range(3)]
    win = numbers[0] == numbers[1] == numbers[2]

    player.attempts -= 1
    player.last_access = datetime.datetime.utcnow()

    if win:
        print(f"Jogador {email} venceu! Números: {numbers}")
        send_email_winner(email)
        player.attempts = 0  # Zerar tentativas após vitória
        db.commit()
        return {"message": "\U0001F389 Parabéns! Você ganhou!", "numbers": numbers, "win": True, "attemptsLeft": 0}

    db.commit()

    if player.attempts > 0:
        return {"message": "Continue tentando!", "numbers": numbers, "win": False, "attemptsLeft": player.attempts}
    else:
        return {"message": "Não foi dessa vez!", "numbers": numbers, "win": False, "attemptsLeft": 0}

# Endpoint para verificar quantas tentativas restam
@app.get("/attempts/{email}")
def get_attempts(email: str, db: Session = Depends(get_db)):
    player = db.query(Player).filter_by(email=email).first()
    if not player:
        return {"message": "Usuário não encontrado"}
    reset_attempts_if_new_day(player, db)
    return {"email": email, "attemptsLeft": player.attempts}

# Rota raiz
@app.get("/")
async def read_root():
    return {"message": "Bem-vindo ao Jackpot do Bolão Animal!"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))  # Usa a porta do ambiente ou 8000 como padrão
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
