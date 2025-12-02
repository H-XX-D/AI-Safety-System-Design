# 🎯 Standalone Mode Guide

## Overview

The AI Safety System GUI can run completely **independently** without requiring the parent AI Safety System components. This makes it perfect for:

- 📊 **Demos and Presentations** - Show off the interface without full system setup
- 🛠️ **Development** - Work on the frontend without backend dependencies
- 📚 **Documentation** - Generate screenshots and videos
- 🎓 **Training** - Teach others about the system architecture
- 🧪 **Testing** - Test UI changes quickly

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd ui
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Start in Standalone Mode (Default)

```bash
python app.py --port 5001
```

That's it! The GUI will automatically run in standalone mode using mock data.

---

## 🔄 Switching Between Modes

### Standalone Mode (Default)
```bash
# Explicitly set standalone mode
STANDALONE=true python app.py --port 5001

# Or just run normally (defaults to standalone)
python app.py --port 5001
```

### Integrated Mode (With Real Components)
```bash
# Requires parent AI Safety System to be installed
STANDALONE=false python app.py --port 5001
```

---

## 📊 What's Included in Standalone Mode

All features work with realistic mock data:

### ✅ Dashboard
- Real-time metrics (simulated)
- Proposal statistics
- Detection accuracy
- System health indicators
- Activity feed with events

### ✅ Proposals View
- 3 example proposals with different statuses:
  - Approved proposal with low deception confidence
  - Rejected proposal with high deception confidence
  - In-review proposal pending debate
- Full filtering and search functionality
- Detailed proposal modals
- CSV export

### ✅ Detection Monitor
- All 7 detection methods with trigger counts
- Performance metrics (accuracy, precision, recall, F1)
- Interactive charts showing method frequency
- Confidence distribution visualization
- Recent detection events timeline

### ✅ Penalties View
- 4 research agents with varying incident histories
- Dual compounding penalty system visualization
- Reward multiplier trends over time
- Approval rate comparisons
- Incident timeline

### ✅ System Health
- Resource monitoring (CPU, memory, disk, network)
- Component status (6 components)
- Sandbox backend status (Docker, Firecracker)
- Test suite results (131 passing)
- WORM manifest verification status

### ✅ Configuration
- All configuration tabs functional
- Detection settings (threshold, methods, weights)
- Penalty configuration (multipliers, thresholds)
- Sandbox settings (backend, limits)
- Agent configuration (limits, capabilities)
- System settings (logging, backup, emergency)

---

## 🎨 Mock Data Details

The standalone mode provides realistic, dynamic data:

### Proposals
```javascript
{
  id: 'prop_001',
  agent_id: 'agent_01',
  status: 'approved',
  component: 'alignment_filter',
  description: 'Improve overconfidence detection',
  deception_confidence: 0.08,
  reward: 58.25,
  debate_votes: [1, 1, 1, 1, 1]
}
```

### Detection Stats
```javascript
{
  total_evaluated: 245,
  deception_detected: 19,
  accuracy: 0.78,
  precision: 0.94,
  recall: 0.78,
  f1_score: 0.85,
  methods: { /* 7 detection methods */ }
}
```

### Agents
```javascript
{
  id: 'agent_01',
  name: 'Research Agent Alpha',
  penalty_multiplier: 1.0,
  incidents: 0,
  total_rewards: 1245.50,
  approval_rate: 0.82
}
```

---

## 🔌 Real-Time Features in Standalone

Even in standalone mode, you get:

- ✅ **Socket.IO Updates** - Simulated real-time data
- ✅ **Live Charts** - Dynamic Chart.js visualizations
- ✅ **Interactive Filters** - All filtering works client-side
- ✅ **Export Functions** - Generate CSV/JSON from mock data
- ✅ **Emergency Controls** - UI functions (no backend action)

---

## 🛠️ Customizing Mock Data

Want to customize the demo data? Edit these sections in `app.py`:

### Proposals Data
```python
# Around line 115
proposals = [
    {
        'id': 'prop_001',
        'agent_id': 'agent_01',
        # ... add your custom data
    }
]
```

### Detection Stats
```python
# Around line 159
stats = {
    'total_evaluated': 245,
    'deception_detected': 19,
    # ... customize metrics
}
```

### Agent Data
```python
# Around line 185
agents = [
    {
        'id': 'agent_01',
        'name': 'Research Agent Alpha',
        # ... customize agent info
    }
]
```

---

## 🎓 Use Cases

### 1. Demo for Stakeholders
```bash
# Start on a clean port
python app.py --port 8080

# Open in browser
open http://localhost:8080
```

### 2. UI Development
```bash
# Enable debug mode for auto-reload
export FLASK_ENV=development
python app.py --port 5001

# Make changes to templates/CSS
# Server auto-reloads on file changes
```

### 3. Screenshot Generation
```bash
# Start server
python app.py --port 5001

# Navigate to each view and capture
open http://localhost:5001/proposals
open http://localhost:5001/detection
open http://localhost:5001/penalties
# etc.
```

### 4. Training Sessions
```bash
# Start server for multiple users on network
python app.py --host 0.0.0.0 --port 5001

# Share URL: http://<your-ip>:5001
```

---

## ⚡ Performance in Standalone Mode

Standalone mode is **ultra-fast** because:

- ✅ No database queries
- ✅ No complex computations
- ✅ Instant API responses
- ✅ Minimal memory usage (~50 MB)
- ✅ No external dependencies

**Typical response times:**
- Dashboard: < 50ms
- API calls: < 10ms
- Page loads: < 200ms

---

## 🔐 Security Notes

Standalone mode:
- ✅ Safe for public demos (no real data)
- ✅ No authentication required (demo only)
- ✅ CORS enabled (for development)
- ⚠️ **Not for production deployment**
- ⚠️ **No sensitive data**

For production, use integrated mode with proper security.

---

## 📦 Deployment Options

### Local Development
```bash
python app.py --port 5001
```

### Docker Container
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY ui /app
RUN pip install -r requirements.txt
ENV STANDALONE=true
CMD ["python", "app.py", "--port", "5001"]
```

### Cloud Deployment (Demo)
Deploy to Heroku, Railway, or similar:
```bash
# Procfile
web: python app.py --port $PORT --host 0.0.0.0
```

---

## 🆚 Standalone vs Integrated

| Feature | Standalone | Integrated |
|---------|-----------|------------|
| **Setup Time** | < 1 minute | 10-15 minutes |
| **Dependencies** | Flask only | Full system |
| **Data** | Mock/Demo | Real/Live |
| **Performance** | Ultra-fast | Production-grade |
| **Use Case** | Demo/Dev | Production |
| **Memory** | ~50 MB | ~500 MB |

---

## 🐛 Troubleshooting

### Server Won't Start in Standalone
**Problem**: Import errors despite standalone mode

**Solution**: Check STANDALONE environment variable:
```bash
echo $STANDALONE  # Should be 'true' or empty (defaults to true)
STANDALONE=true python app.py --port 5001
```

### Port Already in Use
**Problem**: Port 5001 taken

**Solution**: Use different port:
```bash
python app.py --port 8080
```

### No Data Showing
**Problem**: Blank views

**Solution**: Check browser console for errors:
1. Open browser DevTools (F12)
2. Check Console tab
3. Look for JavaScript errors
4. Try hard refresh (Ctrl+Shift+R)

---

## 💡 Tips & Tricks

1. **Quick Demo Setup**: Use startup script
   ```bash
   ./start_server.sh
   ```

2. **Multiple Instances**: Run on different ports
   ```bash
   python app.py --port 5001 &
   python app.py --port 5002 &
   ```

3. **Network Access**: Make available on LAN
   ```bash
   python app.py --host 0.0.0.0 --port 5001
   # Access from other devices: http://<your-ip>:5001
   ```

4. **Custom Theme**: Edit `static/css/main.css` CSS variables

---

## 📚 Additional Resources

- [README.md](README.md) - Complete documentation
- [QUICKSTART.md](QUICKSTART.md) - 30-second setup guide
- [Main Repository](../) - Full AI Safety System

---

**Questions?** Open an issue on GitHub or check the main documentation.

**Want to contribute?** PRs welcome for new mock data scenarios or UI improvements!
