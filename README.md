# EnerBit Tariff Dashboard

Este proyecto es una plataforma full-stack para la abstracción, extracción matemática e ingesta de PDFs de resoluciones tarifarias de operadores de red (Afinia, Enel, etc.). Consiste en un potente backend en Python (FastAPI) con un motor de lectura espacial (pdfplumber), y un dashboard profesional en React (Vite) para la revisión y control de las tarifas.

## 🗂 Estructura del Proyecto

```text
jacaton/
├── backend/                # Lógica del servidor y extracción de PDFs
│   ├── main.py             # API principal FastAPI y algoritmo de extracción
│   ├── database.py         # Conexión local SQLite y esquemas de BD (SQLAlchemy)
│   └── pdfs_de_prueba/     # Carpeta para pruebas (¡Los PDFs aquí dentro se ignoran en git!)
├── frontend/               # Aplicación React web
│   ├── src/                # Código fuente UI
│   └── package.json        # Dependencias de Node
├── test_scripts/           # Scripts satélites aislados para debugear coordenadas
└── .venv/                  # Entorno virtual de dependencias de Python
```

## 🛠 Requisitos Previos

Antes de comenzar, asegúrate de tener instalados los siguientes componentes en tu máquina:
- **Node.js** (v18 o superior)
- **Python** (v3.9 o superior)
- Git

---

## 🚀 Inicialización para Inicializar el Entorno Local

Sigue estos dos pasos para arrancar ambos servidores en terminales separadas.

### 1. Inicializar el Backend (FastAPI + Python)
1. Abre tu terminal en la raíz del proyecto (`jacaton/`).
2. Activa el entorno virtual de Python incluido:
   ```bash
   source .venv/bin/activate
   ```
   *(Si el entorno no cuenta con dependencias actualizadas, corra `pip install fastapi uvicorn sqlalchemy pdfplumber python-multipart`)*
3. Cambia al directorio del backend:
   ```bash
   cd backend
   ```
4. Inicia el servidor de desarrollo en caliente:
   ```bash
   uvicorn main:app --reload
   ```
   *El servidor correrá exitosamente en: http://localhost:8000*

### 2. Inicializar el Frontend (React + Vite)
1. Abre una **nueva ventana/pestaña** de la terminal en la raíz del proyecto.
2. Navega a la carpeta del frontend:
   ```bash
   cd frontend
   ```
3. Instala las dependencias necesarias de Node:
   ```bash
   npm install
   ```
4. Levanta el servidor del dashboard:
   ```bash
   npm run dev
   ```
   *La app abrirá en tu navegador (usualmente http://localhost:5173).*

---

## 🔍 Notas Adicionales sobre el Algoritmo de Extracción
La extracción de las variables núcleo de tarifas (**Generación [G], STN [T], y Restricciones [R]**) fue reconstruida para utilizar **Cajas de Coordenadas X**. Se extrae leyendo la geometría del PDF en lugar de texto plano para blindar la app contra tablas fusionadas y cruces de texto corruptos en los PDFs oficiales de resolución.
Si un PDF en el futuro altera sus márgenes agresivamente, el ajuste deberá hacerse iterando sobre las coordenadas designadas en la función principal en `backend/main.py`.

Los scripts ubicados en `test_scripts/` te sirven si necesitas imprimir matrices de coordenadas matemáticas para un nuevo operador de red distinto.
