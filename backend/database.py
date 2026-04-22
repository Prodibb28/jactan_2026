from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Configuramos la base de datos local SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///./registros.db"

# engine es el motor que conecta a la base de datos
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# 1. Tabla Principal: Representa UN archivo PDF guardado, con su fecha y operador
class Documento(Base):
    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    operador_red = Column(String, index=True)  # Ej. "Afinia" o "Enel"
    mes = Column(Integer, index=True)
    anio = Column(Integer, index=True)

    # Relación "Uno a Muchos": Un documento tiene muchos registros/niveles
    registros = relationship("RegistroTarifario", back_populates="documento", cascade="all, delete-orphan")

# 2. Tabla Secundaria: Representa las filas extraídas de ese documento
class RegistroTarifario(Base):
    __tablename__ = "registros_tarifarios"

    id = Column(Integer, primary_key=True, index=True)
    documento_id = Column(Integer, ForeignKey("documentos.id")) # Clave Foránea
    fila = Column(String)
    
    # Valores de esa fila
    gen = Column(Float, nullable=True)
    stn = Column(Float, nullable=True)
    res = Column(Float, nullable=True)
    d_val = Column(Float, nullable=True)
    c_val = Column(Float, nullable=True)
    cu_val = Column(Float, nullable=True)
    cot_val = Column(Float, nullable=True)
    ot_val = Column(Float, nullable=True)
    pr_val = Column(Float, nullable=True)

    # Relación inversa al documento padre
    documento = relationship("Documento", back_populates="registros")

# 3. Tabla Anual Plan enerPro: Parámetros atados a Comercializadores
class ParametrosOperador(Base):
    __tablename__ = "parametros_operador"

    id = Column(Integer, primary_key=True, index=True)
    operador_red = Column(String, index=True) 
    anio = Column(Integer, index=True)
    fijabit_hogar = Column(Float, nullable=True)
    fijabit_comercial = Column(Float, nullable=True)

# 4. Tabla Anual Plan enerPro: Cargos Globales de Medición Universales
class CargosGlobales(Base):
    __tablename__ = "cargos_globales"

    id = Column(Integer, primary_key=True, index=True)
    anio = Column(Integer, index=True, unique=True)
    
    # Mercado Hogar
    medida_directa_hogar = Column(Float, nullable=True)
    medida_directa_zc = Column(Float, nullable=True)
    medida_semi_indirecta_zc = Column(Float, nullable=True)
    
    # Mercado Comercial
    medida_directa_comercial = Column(Float, nullable=True)
    medida_semi_indirecta_comercial = Column(Float, nullable=True)

# Crea las tablas
Base.metadata.create_all(bind=engine)
