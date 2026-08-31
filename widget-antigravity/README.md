# ⚡ Antigravity Quota Monitor

**Antigravity Quota Monitor** es una aplicación de escritorio nativa y moderna para **Windows 10 / 11** diseñada como un widget flotante que monitorea y visualiza en tiempo real las cuotas y límites restantes de los modelos de inteligencia artificial disponibles en **Google Antigravity**.

---

## 📸 Características Principales

- **Obtención 100% Directa y Oficial**: Consulta el endpoint local Connect-RPC del servidor de lenguaje (`language_server`) de Antigravity. Sin OCR, sin clics simulados y sin riesgo de imprecisiones.
- **Sin Exposición de Credenciales**: Reutiliza de forma segura el token de sesión local existente (`x-codeium-csrf-token`). No pide contraseñas, no almacena claves ni envía datos a servidores externos.
- **Agrupación Inteligente de Cuotas**: Detecta y agrupa automáticamente modelos por bolsa de cuota compartida:
  - **Gemini Models** (Gemini 3.7 Flash, 3.6 Flash, 3.5 Flash, 3.1 Pro, etc.)
  - **Claude & GPT Models** (Claude Opus 4.6, Claude Sonnet 4.6, GPT-OSS 120B, etc.)
  - Nuevas categorías y modelos que Antigravity añada dinámicamente en el futuro.
- **Indicadores Visuales por Color**:
  - 🟢 **70% – 100%**: Normal (Verde Esmeralda)
  - 🟡 **30% – 69%**: Advertencia (Ámbar)
  - 🔴 **0% – 29%**: Crítico (Rojo Coral)
- **Cuenta Regresiva de Reseteo**: Muestra en tiempo real cuánto tiempo falta para la renovación de la cuota (ej. `Resets in 2h 45m`).
- **Diseño Moderno & Glassmorphism**:
  - Ventana flotante sin bordes estándar ("Frameless").
  - Fondo oscuro con efecto translúcido y sombras suaves.
  - Arrastrable y redimensionable libremente sobre el escritorio.
  - Recuerda automáticamente su última posición y tamaño.
- **Modo Compacto (Mini Widget)**: Alterna con un clic entre el monitor completo y una pequeña pastilla flotante (`⚡ AG QUOTA`).
- **Bandeja del Sistema (System Tray)**:
  - Icono dinámico en la barra de tareas.
  - Tooltip informativo con los porcentajes actuales.
  - Menú contextual: Mostrar/Ocultar, Modo Compacto, Refrescar ahora, Configuración, Iniciar con Windows, Salir.
- **Historial y Gráfico de Consumo**: Gráfico interactivo integrado para observar la evolución temporal de la cuota (1h, 6h, 24h, 7d).
- **Inicio Automático con Windows**: Activación con un solo clic desde la configuración sin instalar servicios innecesarios.
- **Manejo de Errores & Resiliencia**: Si Antigravity se cierra o no está disponible, el widget muestra el último estado conocido indicando claramente la hora de la última actualización exitosa.

---

## 🛠️ Arquitectura Técnica

| Componente | Tecnología |
|---|---|
| **Lenguaje** | Python 3.14+ |
| **Framework GUI** | PySide6 (Qt 6.11) |
| **Protocolo de Datos** | HTTP / Connect-RPC local |
| **Persistencia** | SQLite (Historial) + JSON (Configuración) |
| **Empaquetado** | PyInstaller (Ejecutable `.exe` standalone) |
| **Instalador** | Inno Setup 6 (Instalador Windows con desinstalador) |

---

## 🚀 Instalación y Uso

### Método 1: Instalador Oficial de Windows (Recomendado)

1. Ejecuta el archivo instalador:
   ```
   dist/installer/AntigravityQuotaMonitor-Setup.exe
   ```
2. Sigue el asistente de instalación. Puedes elegir crear accesos directos en el Escritorio, Menú Inicio o inicio automático con Windows.
3. El desinstalador estará disponible en *Configuración de Windows > Aplicaciones instaladas*.

### Método 2: Ejecutable Portable Standalone

Si prefieres no instalar nada, puedes ejecutar directamente el archivo independiente:
```
dist/AntigravityQuotaMonitor.exe
```

### Método 3: Ejecución desde Código Fuente

1. Clona o abre el directorio del proyecto:
   ```bash
   cd widget-antigravity
   ```
2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Inicia la aplicación:
   ```bash
   python src/main.py
   ```

---

## ⚙️ Compilación desde el Código Fuente

Para recompilar el ejecutable y el instalador de forma automática:

```bash
# Ejecutar el script automatizado (limpieza, PyInstaller e Inno Setup)
build_all.bat
```

O manualmente:
```bash
# 1. Compilar ejecutable independiente con PyInstaller
python -m PyInstaller build.spec --clean -y

# 2. Compilar instalador con Inno Setup
iscc installer\installer.iss
```

---

## 🔍 Método de Obtención de Cuotas

Durante la investigación técnica se descubrió que Google Antigravity ejecuta localmente un proceso servidor de lenguaje (`language_server_windows_x64.exe`) que expone una interfaz RPC local:

- **Endpoint**: `http://127.0.0.1:<puerto>/exa.language_server_pb.LanguageServerService/GetUserStatus`
- **Cabecera de autenticación**: `x-codeium-csrf-token: <csrf_token>`
- **Descubrimiento dinámico**: La aplicación detecta en segundo plano el proceso activo, extrae el token `--csrf_token` de sus argumentos de ejecución y ubica el puerto TCP de escucha HTTP activo.

---

## 🔒 Privacidad y Seguridad

- **100% Local**: No se transmiten datos a servidores de terceros ni a la nube.
- **Sin almacenamiento de credenciales**: No se solicitan ni guardan contraseñas.
- **Solo lectura**: La aplicación únicamente consulta el estado del usuario mediante peticiones locales en `127.0.0.1`.

---

## 📄 Licencia

MIT License. Desarrollado como una herramienta de productividad para la comunidad de Google Antigravity.
