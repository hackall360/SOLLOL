# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Features

### 1. API Key Authentication

SOLLOL supports API key-based authentication for production deployments.

**Enable Authentication**:
```python
from sollol import SOLLOL, SOLLOLConfig
from sollol.auth import get_auth_manager, PERM_CHAT, PERM_ADMIN

# Create API keys
auth = get_auth_manager()

# Admin key with full access
admin_key = auth.create_api_key(
    name="admin",
    permissions=[PERM_ADMIN],
    rate_limit=10000
)
print(f"Admin key (save this!): {admin_key}")

# User key with limited access
user_key = auth.create_api_key(
    name="app-user",
    permissions=[PERM_CHAT, PERM_EMBED],
    rate_limit=1000
)
print(f"User key: {user_key}")

# Start SOLLOL with auth enabled
config = SOLLOLConfig(
    auth_enabled=True,
    hosts=["localhost:11434"]
)
sollol = SOLLOL(config)
sollol.start()
```

**Use API Keys**:
```python
from sollol import SOLLOLClient, SOLLOLConfig

config = SOLLOLConfig(
    base_url="http://localhost:8000",
    api_key="your-api-key-here"
)
client = SOLLOLClient(config)

# All requests now include API key
response = client.chat("Hello!")
```

**Or with headers**:
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.2", "messages": [...]}'
```

### 2. Rate Limiting

API keys have configurable rate limits (requests per hour).

**Configure Rate Limits**:
```python
# High-priority user: 10,000 requests/hour
premium_key = auth.create_api_key(
    name="premium-user",
    permissions=[PERM_CHAT, PERM_EMBED, PERM_BATCH],
    rate_limit=10000
)

# Free tier: 100 requests/hour
free_key = auth.create_api_key(
    name="free-user",
    permissions=[PERM_CHAT],
    rate_limit=100
)
```

**Rate Limit Response**:
```json
{
  "detail": "Rate limit exceeded",
  "status_code": 429
}
```

### 3. Role-Based Access Control (RBAC)

Permissions control access to different endpoints.

**Available Permissions**:
- `chat`: Access to `/api/chat`
- `embed`: Access to `/api/embed`
- `batch`: Access to `/api/embed/batch`
- `stats`: Access to `/api/stats`
- `health`: Access to `/api/health`
- `admin`: Full access to all endpoints + admin functions

**Example: Read-Only Key**:
```python
readonly_key = auth.create_api_key(
    name="monitoring",
    permissions=[PERM_HEALTH, PERM_STATS],
    rate_limit=5000
)
# Can check health and stats, but cannot make inference requests
```

### 4. Key Rotation

Rotate API keys periodically for security.

**Revoke and Replace**:
```python
# Revoke old key
auth.revoke_api_key(old_key)

# Create new key
new_key = auth.create_api_key(
    name="app-user-rotated",
    permissions=[PERM_CHAT, PERM_EMBED],
    rate_limit=1000
)
```

### 5. Network Security

**Production Recommendations**:

1. **Use HTTPS**: Always run SOLLOL behind HTTPS in production
   ```python
   # Use nginx or Traefik for TLS termination
   # SOLLOL runs on HTTP internally, proxy adds HTTPS
   ```

2. **Firewall Rules**: Restrict access to SOLLOL gateway
   ```bash
   # Only allow access from application servers
   iptables -A INPUT -p tcp --dport 8000 -s 10.0.0.0/24 -j ACCEPT
   iptables -A INPUT -p tcp --dport 8000 -j DROP
   ```

3. **VPC/Network Isolation**: Deploy in private network
   ```yaml
   # Docker Compose with isolated network
   networks:
     sollol-internal:
       driver: bridge
       internal: true
   ```

### 6. Input Validation

SOLLOL validates all inputs to prevent injection attacks.

**Protections**:
- ✅ Request payload size limits
- ✅ JSON schema validation
- ✅ Model name whitelisting
- ✅ Priority value bounds (1-10)
- ✅ Host address validation

### 7. Secrets Management

**Never commit secrets**:
```python
import os

# Load API keys from environment
admin_key = os.environ.get("SOLLOL_ADMIN_KEY")
if not admin_key:
    admin_key = auth.create_api_key(...)
    # Save to secure vault (not code!)
```

**Use Environment Variables**:
```bash
export SOLLOL_ADMIN_KEY="your-admin-key"
export SOLLOL_DB_PASSWORD="your-db-password"
python app.py
```

**Or Secret Management Service**:
```python
# AWS Secrets Manager
import boto3

secrets = boto3.client('secretsmanager')
api_key = secrets.get_secret_value(SecretId='sollol/api-key')['SecretString']
```

## Reporting a Vulnerability

**Do NOT open a public issue for security vulnerabilities.**

Instead:

1. **Email**: security@sollol.dev (if available)
2. **Private Disclosure**: Use GitHub's private vulnerability reporting
3. **Encrypted**: Use PGP key (available on keybase.io/sollol)

**Include**:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

**Response Timeline**:
- **24 hours**: Initial acknowledgment
- **7 days**: Preliminary assessment
- **30 days**: Fix or mitigation plan
- **90 days**: Public disclosure (if agreed)

## Security Best Practices

### For Development

✅ **Do**:
- Use authentication in production
- Rotate API keys regularly (every 90 days)
- Monitor rate limits and anomalies
- Keep dependencies updated
- Use HTTPS/TLS for all traffic
- Implement logging and audit trails

❌ **Don't**:
- Commit API keys to git
- Use default/weak keys
- Disable authentication in production
- Expose SOLLOL directly to internet
- Use HTTP in production
- Share API keys between environments

### For Production Deployment

```yaml
# Example: Secure Docker Compose
version: '3.8'

services:
  sollol:
    image: sollol:latest
    environment:
      - SOLLOL_AUTH_ENABLED=true
      - SOLLOL_ADMIN_KEY_FILE=/run/secrets/admin_key
    secrets:
      - admin_key
    networks:
      - internal
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G

  nginx:
    image: nginx:latest
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/ssl:ro
    ports:
      - "443:443"
    networks:
      - internal
      - public
    depends_on:
      - sollol

secrets:
  admin_key:
    external: true

networks:
  internal:
    driver: bridge
    internal: true
  public:
    driver: bridge
```

### Monitoring & Alerts

**Track Security Events**:
```python
# Log authentication failures
@app.middleware("http")
async def log_auth_failures(request: Request, call_next):
    response = await call_next(request)
    if response.status_code == 401:
        logger.warning(f"Auth failure: {request.client.host}")
    return response
```

**Set Up Alerts**:
- Failed authentication attempts (>10/min)
- Rate limit violations
- Unusual traffic patterns
- New API key creation
- Permission changes

## Compliance

SOLLOL is designed to support:

- **SOC 2**: Audit logging, access controls, encryption
- **GDPR**: Data minimization, right to deletion
- **HIPAA**: Encryption at rest and in transit (when configured)

**Note**: Compliance requires proper deployment configuration. SOLLOL provides the tools, but deployment must follow best practices.

## Security Updates

Subscribe to security announcements:
- **GitHub**: Watch releases
- **RSS**: Subscribe to release feed
- **Email**: security-announce@sollol.dev

## Acknowledgments

We appreciate responsible disclosure. Security researchers who report valid vulnerabilities will be:

- Acknowledged in SECURITY.md (if desired)
- Listed in release notes
- Eligible for bounty (if program active)

---

**Last Updated**: 2025-10-03
**Security Contact**: Open an issue or email maintainers
