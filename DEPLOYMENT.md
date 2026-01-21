# Deployment Guide - Canadian Legal News Pipeline

This guide covers deploying the Legal News Pipeline to Streamlit Community Cloud.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Streamlit Community Cloud Deployment](#streamlit-community-cloud-deployment)
3. [Environment Variables & Secrets](#environment-variables--secrets)
4. [Post-Deployment Configuration](#post-deployment-configuration)
5. [Troubleshooting](#troubleshooting)
6. [Alternative Deployment Options](#alternative-deployment-options)

---

## Prerequisites

### Required Accounts
- GitHub account (for repository hosting)
- Streamlit Community Cloud account (free at https://streamlit.io/cloud)
- Anthropic API key (for Claude AI article generation)
- Google API key (for Gemini topic extraction)

### Required API Keys
1. **Anthropic API Key**: Get from https://console.anthropic.com/
2. **Google AI API Key**: Get from https://aistudio.google.com/app/apikey

---

## Streamlit Community Cloud Deployment

### Step 1: Push to GitHub

1. **Initialize Git Repository** (if not already done):
   ```bash
   cd /path/to/Automated_news_pipeline
   git init
   git add .
   git commit -m "Initial commit - Legal News Pipeline"
   ```

2. **Create GitHub Repository**:
   - Go to https://github.com/new
   - Name: `canadian-legal-news-pipeline` (or your choice)
   - Keep it **Public** (required for Streamlit free tier)
   - Do NOT initialize with README (you already have one)

3. **Push to GitHub**:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/canadian-legal-news-pipeline.git
   git branch -M main
   git push -u origin main
   ```

### Step 2: Deploy to Streamlit Cloud

1. **Sign in to Streamlit Cloud**:
   - Go to https://share.streamlit.io/
   - Sign in with GitHub

2. **Create New App**:
   - Click "New app"
   - Select your repository: `YOUR_USERNAME/canadian-legal-news-pipeline`
   - Main file path: `streamlit_app.py`
   - App URL: Choose a custom URL (e.g., `legal-news-pipeline`)

3. **Advanced Settings** (before deploying):
   - Python version: `3.11` (matches runtime.txt)
   - Click "Deploy!"

### Step 3: Configure Secrets

After deployment starts, immediately configure secrets:

1. **Access Secrets Panel**:
   - In Streamlit Cloud dashboard, click on your app
   - Click the "⚙️ Settings" button
   - Go to "Secrets" tab

2. **Add Required Secrets** (TOML format):
   ```toml
   # Authentication password for the app
   PASSWORD = "your-secure-password-here"

   # API Keys
   ANTHROPIC_API_KEY = "sk-ant-your-anthropic-key-here"
   GOOGLE_API_KEY = "your-google-api-key-here"
   ```

3. **Save Secrets**:
   - Click "Save"
   - App will automatically restart with new secrets

---

## Environment Variables & Secrets

### How Secrets Work

The app reads secrets in this priority order:
1. **Streamlit Secrets** (`st.secrets`) - Used in production
2. **Environment Variables** (`os.environ`) - Fallback for local development
3. **`.env` file** - Local development only (not deployed)

### Local Development Setup

For local testing with secrets:

1. **Copy secrets template**:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

2. **Edit `.streamlit/secrets.toml`**:
   ```toml
   PASSWORD = "dev-password"
   ANTHROPIC_API_KEY = "sk-ant-your-key"
   GOOGLE_API_KEY = "your-google-key"
   ```

3. **Never commit secrets.toml**:
   - Already in `.gitignore`
   - Only use for local testing

### Required Secrets

| Secret | Description | Where to Get |
|--------|-------------|--------------|
| `PASSWORD` | App authentication password | Choose a secure password |
| `ANTHROPIC_API_KEY` | Claude AI API key | https://console.anthropic.com/ |
| `GOOGLE_API_KEY` | Gemini AI API key | https://aistudio.google.com/app/apikey |

---

## Post-Deployment Configuration

### Initial Database Setup

The app creates an SQLite database automatically on first run. No manual setup needed.

### First-Time Usage

1. **Access Your App**:
   - Visit: `https://your-app-name.streamlit.app`
   - Enter password (from secrets)

2. **Fetch Initial Articles**:
   - Go to "📥 Fetch Articles" page
   - Select sources to scrape
   - Click "Start Fetching"

3. **Process Topics**:
   - Go to "⚙️ Process Topics" page
   - Select unprocessed articles
   - Click "Start Processing"

4. **Generate Articles**:
   - Go to "✍️ Generate Articles" page
   - Browse topics
   - Select topics to generate

### Database Management

- **Location**: `data/pipeline.db` (created automatically)
- **Backups**: Download from app (future feature) or access via Streamlit Cloud shell
- **Reset**: Delete `data/pipeline.db` to start fresh

---

## Troubleshooting

### Common Issues

#### 1. "Module not found" errors

**Cause**: Missing dependencies in `requirements.txt`

**Solution**:
```bash
# Locally, verify all imports work
python -c "import streamlit; import anthropic; import google.genai"

# If missing, add to requirements.txt and push
git add requirements.txt
git commit -m "Fix: Add missing dependencies"
git push
```

#### 2. "API Key not found" errors

**Cause**: Secrets not configured properly

**Solution**:
- Check Streamlit Cloud secrets (Settings → Secrets)
- Ensure key names match exactly: `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`
- No quotes around values in TOML format
- Click "Save" after editing

#### 3. Database errors

**Cause**: Database file permissions or corruption

**Solution**:
- Streamlit Cloud has persistent storage in `data/` directory
- If corrupted, delete via app management console
- Database will recreate on next run

#### 4. Memory errors

**Cause**: Free tier has 1GB memory limit

**Solution**:
- Limit batch operations (process 10-20 articles at a time)
- Use Claude Haiku instead of Sonnet for generation (cheaper, faster)
- Clear cached data periodically

#### 5. App is slow or timing out

**Cause**: Long-running operations

**Solution**:
- Article generation can take 1-2 minutes per article
- Use batch generation sparingly
- Consider upgrading to Streamlit Teams for better performance

### Logs & Debugging

1. **View Live Logs**:
   - Streamlit Cloud dashboard → Your app → "Manage app" → "Logs"
   - Shows real-time stdout/stderr

2. **App Logs Tab**:
   - Built-in logs viewer in Streamlit Cloud
   - Filter by severity (info, warning, error)

3. **Local Testing**:
   ```bash
   # Run locally to debug before deploying
   streamlit run streamlit_app.py
   ```

### Restarting the App

1. **From Dashboard**:
   - Go to app in Streamlit Cloud
   - Click "⋮" menu → "Reboot app"

2. **Force Redeploy**:
   ```bash
   # Push any change to trigger redeploy
   git commit --allow-empty -m "Force redeploy"
   git push
   ```

---

## Alternative Deployment Options

### Option 2: Heroku Deployment

You already have Heroku configuration files (`Procfile`, `runtime.txt`).

**Steps**:
1. Create Heroku account
2. Install Heroku CLI
3. Deploy:
   ```bash
   heroku create your-app-name
   heroku config:set PASSWORD=your-password
   heroku config:set ANTHROPIC_API_KEY=your-key
   heroku config:set GOOGLE_API_KEY=your-key
   git push heroku main
   ```

**Note**: Heroku no longer has a free tier. Starting at $7/month.

### Option 3: Railway Deployment

Modern Heroku alternative with generous free tier.

**Steps**:
1. Go to https://railway.app/
2. Sign in with GitHub
3. "New Project" → "Deploy from GitHub repo"
4. Select your repository
5. Add environment variables in dashboard
6. Deploy automatically

**Benefits**:
- $5 free credit per month
- Easy database add-ons
- Automatic deployments

### Option 4: Self-Hosted (Docker)

For full control, deploy on your own server.

**Create Dockerfile**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

**Deploy**:
```bash
docker build -t legal-news-pipeline .
docker run -p 8501:8501 \
  -e PASSWORD=your-password \
  -e ANTHROPIC_API_KEY=your-key \
  -e GOOGLE_API_KEY=your-key \
  legal-news-pipeline
```

---

## Cost Estimates

### Streamlit Community Cloud
- **Hosting**: FREE (for public apps)
- **Limitations**: 1GB RAM, 1 CPU, shared resources
- **Upgrade**: Streamlit Teams ($250/month) for private apps and better resources

### API Costs
- **Claude Sonnet 4.5**: ~$0.12 per article generated
- **Claude Haiku 4.5**: ~$0.01 per article generated (recommended)
- **Gemini 2.5 Flash**: ~$0.001 per article processed (topic extraction)

**Estimated Monthly Costs** (100 articles/month):
- Topic extraction: $0.10 (Gemini)
- Article generation: $1-12 (Haiku vs Sonnet)
- **Total**: $1-12/month in API costs

---

## Security Best Practices

1. **Never commit secrets**:
   - Use `.gitignore` for `.env` and `secrets.toml`
   - Use environment variables in production

2. **Change default password**:
   - Default is "changeme" - CHANGE IT!
   - Use strong password (12+ characters)

3. **API Key Security**:
   - Never expose API keys in logs
   - Rotate keys periodically
   - Use separate keys for dev/prod

4. **Database Backups**:
   - Export database regularly
   - Store backups securely
   - Test restore procedures

---

## Monitoring & Maintenance

### Regular Tasks

1. **Weekly**:
   - Check error logs
   - Monitor API usage/costs
   - Review generated articles

2. **Monthly**:
   - Database backup
   - Update dependencies
   - Security patches

3. **As Needed**:
   - Add new legal sources
   - Adjust topic extraction prompts
   - Tune SMB relevance scoring

### Updates & Upgrades

**Updating Code**:
```bash
# Make changes locally
git add .
git commit -m "Update: description"
git push

# Streamlit Cloud auto-deploys on push
```

**Updating Dependencies**:
```bash
# Update requirements.txt
pip freeze > requirements.txt

# Test locally first
pip install -r requirements.txt
streamlit run streamlit_app.py

# Then push
git add requirements.txt
git commit -m "Update dependencies"
git push
```

---

## Support & Resources

- **Streamlit Docs**: https://docs.streamlit.io/
- **Anthropic API**: https://docs.anthropic.com/
- **Google AI Studio**: https://ai.google.dev/
- **GitHub Issues**: Report bugs in your repository

---

## Quick Reference

### Deployment Checklist

- [ ] Code pushed to GitHub (public repo)
- [ ] Streamlit Cloud account created
- [ ] App deployed from GitHub repo
- [ ] Secrets configured (PASSWORD, API keys)
- [ ] App is accessible and loads
- [ ] Authentication works
- [ ] Can fetch articles
- [ ] Can process topics
- [ ] Can generate articles
- [ ] Database persists between sessions

### Essential URLs

- **App Dashboard**: https://share.streamlit.io/
- **Your App**: https://your-app-name.streamlit.app
- **GitHub Repo**: https://github.com/YOUR_USERNAME/canadian-legal-news-pipeline
- **Anthropic Console**: https://console.anthropic.com/
- **Google AI Studio**: https://aistudio.google.com/

---

## Next Steps

After successful deployment:

1. **Customize branding** (`.streamlit/config.toml`)
2. **Add more legal sources** (extend scrapers in `scrapers/`)
3. **Fine-tune AI prompts** (in `compile.py` and `generate.py`)
4. **Set up scheduled fetching** (cron jobs or Streamlit scheduled reruns)
5. **Add analytics** (track popular topics, usage patterns)

**Happy deploying!** 🚀
