# 🚀 Quick Start Guide

## Getting Started in 30 Seconds

### 1. Navigate to UI Directory
```bash
cd ui
```

### 2. Run the Startup Script
```bash
./start_server.sh
```

Or manually:
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start server (port 5001 to avoid macOS AirPlay on 5000)
python app.py --port 5001
```

### 3. Open in Browser
Visit: **http://localhost:5001**

---

## 📊 Available Views

- **Dashboard** (http://localhost:5001) - Main overview with real-time metrics
- **Proposals** (http://localhost:5001/proposals) - Proposal management and filtering
- **Detection** (http://localhost:5001/detection) - 7-method deception detection monitor
- **Penalties** (http://localhost:5001/penalties) - Agent reputation and penalty tracking
- **System** (http://localhost:5001/system) - System health and performance metrics
- **Config** (http://localhost:5001/config) - System configuration management

---

## 🔧 Custom Port

```bash
# Run on custom port
python app.py --port 8080

# Or set PORT environment variable
PORT=8080 ./start_server.sh
```

---

## ⚠️ Troubleshooting

### Port 5000 Already in Use
**Problem**: macOS AirPlay Receiver uses port 5000 by default.

**Solution**: Use port 5001 (default) or any other available port:
```bash
python app.py --port 5001
```

### Dependencies Not Installed
**Problem**: `ModuleNotFoundError: No module named 'flask'`

**Solution**: Install dependencies in virtual environment:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Server Won't Start
**Problem**: Virtual environment not activated

**Solution**: Always activate venv before running:
```bash
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows
```

---

## 🎨 Features

- ✅ Real-time metrics and updates (Socket.IO)
- ✅ Interactive charts (Chart.js)
- ✅ Dark modern theme
- ✅ Fully responsive design
- ✅ Advanced filtering and search
- ✅ CSV/JSON export functionality
- ✅ Emergency controls
- ✅ Configuration management

---

## 📝 Development Mode

Enable Flask debug mode with auto-reload:
```bash
export FLASK_ENV=development
python app.py --port 5001
```

---

## 🛑 Stopping the Server

Press `Ctrl+C` in the terminal where the server is running.

---

## 📚 More Information

See [README.md](README.md) for complete documentation.
