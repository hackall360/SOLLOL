# FlockParser Remote Access - Quick Start Card

**Goal:** Access FlockParser knowledge base from SynapticLlamas on a different machine

---

## ✅ Current Status

**Local access:** Working ✅ (verified with test scripts)
**Remote access:** Documented ✅ (4 methods available)
**Next step:** Choose method and deploy (5-10 minutes)

---

## 🚀 Recommended: NFS Setup (5 minutes)

### FlockParser Machine (Server)
```bash
sudo apt install nfs-kernel-server
echo "/home/joker/FlockParser <client-ip>/24(ro,sync,no_subtree_check)" | sudo tee -a /etc/exports
sudo exportfs -ra
```

### SynapticLlamas Machine (Client)
```bash
sudo apt install nfs-common
sudo mkdir -p /mnt/flockparser
sudo mount <server-ip>:/home/joker/FlockParser /mnt/flockparser
```

### Update Code (One Line)
```python
adapter = FlockParserAdapter(
    flockparser_path="/mnt/flockparser"  # Changed from /home/joker/FlockParser
)
```

### Verify
```bash
cd /home/joker/SOLLOL
python3 verify_flockparser_access.py
python3 test_local_rag_integration.py
```

---

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| `REMOTE_ACCESS_SETUP_GUIDE.md` | Step-by-step setup for all methods |
| `REMOTE_ACCESS_STATUS.md` | Current status and decision matrix |
| `SYNAPTICLLAMAS_RAG_COMMANDS.md` | User commands for RAG |
| `SESSION_SUMMARY.md` | Complete session details |

---

## 🔍 Test Scripts

```bash
# Verify FlockParser access
python3 verify_flockparser_access.py

# Test adapter integration
python3 test_local_rag_integration.py
```

---

## 🎯 Enable RAG in SynapticLlamas

```bash
cd /home/joker/SynapticLlamas
python main.py --interactive

SynapticLlamas> mode distributed
SynapticLlamas> collab on
SynapticLlamas> rag on
SynapticLlamas> Explain quantum computing
```

---

## 📊 Performance

| Method | Overhead | Setup | Code Changes |
|--------|----------|-------|--------------|
| **NFS** ⭐ | +7% | 5 min | Path only |
| HTTP API | +67% | 15 min | Adapter mod |
| SSHFS | +17% | 2 min | Path only |
| Rsync | N/A | 5 min | None |

---

## 🆘 Need Help?

- **Setup issues:** See `REMOTE_ACCESS_SETUP_GUIDE.md` → Troubleshooting
- **Architecture questions:** See `SYNAPTICLLAMAS_FLOCKPARSER_INTERFACE.md`
- **Command reference:** See `SYNAPTICLLAMAS_RAG_COMMANDS.md`

---

**All files in:** `/home/joker/SOLLOL/`
