# Quick Start - Deploy in 5 Minutes

Get your Legal News Pipeline running in the cloud in just 5 minutes!

## 🚀 Ultra-Fast Deployment to Streamlit Cloud

### 1. Get Your API Keys (2 minutes)

**Anthropic (Claude AI)**:
- Go to: https://console.anthropic.com/
- Sign up/login
- Click "Get API Key"
- Copy your key (starts with `sk-ant-`)

**Google AI (Gemini)**:
- Go to: https://aistudio.google.com/app/apikey
- Click "Create API Key"
- Copy your key

### 2. Push to GitHub (1 minute)

```bash
# In your project directory
git init
git add .
git commit -m "Initial commit"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

### 3. Deploy to Streamlit (2 minutes)

1. Go to https://share.streamlit.io/
2. Sign in with GitHub
3. Click "New app"
4. Select your repository
5. Main file: `streamlit_app.py`
6. Click "Advanced settings"
7. Add secrets (TOML format):
   ```toml
   PASSWORD = "your-chosen-password"
   ANTHROPIC_API_KEY = "sk-ant-your-key-here"
   GOOGLE_API_KEY = "your-google-key-here"
   ```
8. Click "Deploy!"

### 4. Access Your App

- Your app will be live at: `https://your-app-name.streamlit.app`
- Login with your password
- Start fetching and generating articles!

## 📖 Next Steps

- Read full [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions
- Configure settings in `.streamlit/config.toml`
- Add more legal news sources
- Customize AI prompts

## ⚠️ Important Notes

- **Free Tier**: Streamlit Community Cloud is free for public repos
- **Costs**: Only API usage costs (~$1-12/month depending on generation volume)
- **Security**: Never commit API keys - use Streamlit secrets
- **Performance**: Free tier has 1GB RAM limit - batch operations accordingly

## 🆘 Having Issues?

Check [DEPLOYMENT.md](DEPLOYMENT.md#troubleshooting) for troubleshooting guide.

## 💰 Cost Breakdown

| Service | Cost |
|---------|------|
| Streamlit Hosting | FREE |
| Claude Haiku (per article) | $0.01 |
| Claude Sonnet (per article) | $0.12 |
| Gemini Topic Extraction | ~$0.001 per article |

**Estimated: $1-12/month for 100 articles**

---

**That's it!** Your legal news pipeline is now live! 🎉
