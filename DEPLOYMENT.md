# Deployment Guide for Spotify Visualizer

## 🚀 Deploying to Streamlit Cloud (Recommended)

### Step 1: Prepare Your Repository
Your repo is already ready! It has:
- ✅ `app.py` - Main application
- ✅ `requirements.txt` - Dependencies
- ✅ `.streamlit/config.toml` - Configuration

### Step 2: Create Streamlit Cloud Account
1. Go to [streamlit.io/cloud](https://streamlit.io/cloud)
2. Sign up with your GitHub account
3. Authorize Streamlit to access your repos

### Step 3: Deploy the App
1. Click **"New app"** in Streamlit Cloud
2. Select your GitHub repo: `efeertugrul/spotify-visualization`
3. Choose branch: `main`
4. Set main file path: `app.py`
5. Click **"Deploy"**

### Step 4: Add Spotify Credentials (Secure)
1. Go to your app's Settings (⚙️ icon)
2. Click **"Secrets"**
3. Add your credentials in the secrets editor:

```toml
SPOTIFY_CLIENT_ID = "your_client_id_here"
SPOTIFY_CLIENT_SECRET = "your_client_secret_here"
SPOTIFY_USERNAME = "your_spotify_username"
```

The app will now read from these secure secrets instead of the text inputs!

---

## 🎯 Deploying to Render

### Step 1: Connect Your Repository
1. Go to [render.com](https://render.com)
2. Sign up/Login with GitHub
3. Click **"New+"** → **"Web Service"**
4. Connect your GitHub repo

### Step 2: Configure Service
- **Name**: `spotify-visualizer`
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `streamlit run app.py --server.port 8501 --server.address 0.0.0.0`

### Step 3: Set Environment Variables
In Render dashboard:
1. Go to your service → **Environment**
2. Add variables:
   - `SPOTIFY_CLIENT_ID` = your_client_id
   - `SPOTIFY_CLIENT_SECRET` = your_client_secret
   - `SPOTIFY_USERNAME` = your_username

### Step 4: Deploy
Click **"Deploy"** and Render will automatically deploy on every push to `main`

---

## 🐳 Deploying with Docker

### Create Dockerfile

Save as `Dockerfile` in root:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .
COPY .streamlit .streamlit

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Build & Run Locally
```bash
docker build -t spotify-visualizer .
docker run -p 8501:8501 \
  -e SPOTIFY_CLIENT_ID=your_id \
  -e SPOTIFY_CLIENT_SECRET=your_secret \
  -e SPOTIFY_USERNAME=your_username \
  spotify-visualizer
```

Open `http://localhost:8501`

---

## 💻 Running Locally

```bash
# Clone repo
git clone https://github.com/efeertugrul/spotify-visualization.git
cd spotify-visualization

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "SPOTIFY_CLIENT_ID=your_id" > .env
echo "SPOTIFY_CLIENT_SECRET=your_secret" >> .env
echo "SPOTIFY_USERNAME=your_username" >> .env

# Run app
streamlit run app.py
```

Open `http://localhost:8501`

---

## 📋 Comparison of Deployment Options

| Platform | Cost | Uptime | Setup Time | Ease |
|----------|------|--------|-----------|------|
| **Streamlit Cloud** | Free (1 app) | 24/7 | 5 min | ⭐⭐⭐⭐⭐ |
| **Render** | Free (with limits) | 24/7 | 10 min | ⭐⭐⭐⭐ |
| **Replit** | Free (with limits) | Spinning | 5 min | ⭐⭐⭐⭐ |
| **Docker + Heroku** | Paid | 24/7 | 15 min | ⭐⭐⭐ |

---

## 🔐 Security Best Practices

1. **Never commit secrets** to GitHub
2. Use platform secrets (Streamlit Cloud, Render, etc.)
3. For local development, create `.env` file:
   ```bash
   SPOTIFY_CLIENT_ID=xxx
   SPOTIFY_CLIENT_SECRET=xxx
   SPOTIFY_USERNAME=xxx
   ```

4. Make sure `.env` is in `.gitignore` (it's already there)
5. Never share your Client Secret publicly

---

## 🐛 Troubleshooting

### App crashes on deploy
**Solution:**
- Check `requirements.txt` versions
- Verify Python version (3.9+)
- Check deployment platform logs

### "Spotify API Error"
**Solution:**
- Verify credentials are correct
- Ensure playlists are public
- Check rate limits (Spotify API has limits)

### "Permission denied"
**Solution:**
- Make sure your Spotify profile is public
- Check app settings in [Spotify Dashboard](https://developer.spotify.com/dashboard)

### Slow performance
**Solution:**
- Reduce number of playlists to analyze
- Use Streamlit's caching decorator
- Upgrade to paid tier if needed

---

## 📞 Support & Resources

- **Streamlit Docs**: [docs.streamlit.io](https://docs.streamlit.io)
- **Spotipy Docs**: [spotipy.readthedocs.io](https://spotipy.readthedocs.io)
- **Spotify API**: [developer.spotify.com](https://developer.spotify.com)
- **GitHub Issues**: [Report issues here](https://github.com/efeertugrul/spotify-visualization/issues)

---

## ✅ Deployment Checklist

- [ ] Spotify API credentials obtained
- [ ] Repository pushed to GitHub
- [ ] `requirements.txt` updated
- [ ] Deployment platform selected
- [ ] Secrets/environment variables added
- [ ] App deployed and tested
- [ ] Shared link with others!

---

Happy deploying! 🎉
