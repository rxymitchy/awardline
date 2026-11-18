# Quick Deploy to Vercel with Groq - Step by Step

Your code is now on GitHub: https://github.com/rxymitchy/awardline

## What You'll Need

1. **Groq API Key** (free) - See GROQ_SETUP.md for detailed guide
2. **Vercel Account** (free) - Sign up at https://vercel.com
3. **5 minutes** ⏱️

## Step 1: Get Your Free Groq API Key

1. Go to **https://console.groq.com**
2. Sign up (no credit card required)
3. Click **API Keys** → **Create API Key**
4. Copy your key (starts with `gsk_...`)

💡 **Why Groq?** Free, super fast, perfect for Vercel serverless deployment. No need for Ollama!

## Step 2: Deploy to Vercel

1. Go to **https://vercel.com/new**
2. Click **"Import Git Repository"**
3. Select `rxymitchy/awardline`
4. Add environment variables:

   | Variable | Value |
   |----------|-------|
   | `GROQ_API_KEY` | Your Groq key (gsk_...) |
   | `AWARDLINE_SECRET` | Any random secure string |
   | `GROQ_MODEL` | `llama-3.1-70b-versatile` (optional) |

5. Click **Deploy**

That's it! ✅

## Step 3: Test Your Deployment

1. Vercel will give you a URL: `https://awardline-xxxx.vercel.app`
2. Open it in your browser
3. Login with any name
4. Submit a test quote
5. Watch the agent work with process icons (🔍 searching, ⚖️ comparing, ✍️ writing)

## Environment Variables Explained

### Required:

**GROQ_API_KEY**
- Your Groq API key from https://console.groq.com
- Example: `gsk_abc123xyz...`

**AWARDLINE_SECRET**
- Any random string for session security
- Example: `my-super-secret-key-2024`

### Optional:

**GROQ_MODEL**
- Default: `llama-3.1-70b-versatile` (recommended)
- Alternatives: `llama-3.1-8b-instant` (faster), `mixtral-8x7b-32768` (more context)

## Quick Test Locally First (Optional)

```powershell
# Set your Groq API key
$env:GROQ_API_KEY="gsk_your_key_here"

# Run demo
.\.venv\Scripts\python -m awardline demo
```

If it works locally, it'll work on Vercel! 🚀

## Alternative: Deploy with Vercel CLI

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Add secrets (recommended for sensitive data)
vercel secrets add groq-api-key "gsk_your_key_here"
vercel secrets add awardline-secret "your-secure-random-string"

# Deploy to production
vercel --prod
```

## Groq Rate Limits (Free Tier)

Your free Groq account includes:
- ✅ 30 requests per minute
- ✅ 14,400 requests per day
- ✅ 131,072 tokens per minute

**More than enough for testing and moderate production use!**

## Troubleshooting

### Build fails?
- Check Vercel build logs in dashboard
- Ensure all dependencies are compatible

### "GROQ_API_KEY environment variable is required"
- Go to Vercel project → Settings → Environment Variables
- Add `GROQ_API_KEY` with your key
- Redeploy the project

### Agent not responding?
- Verify your Groq API key is correct
- Check it starts with `gsk_`
- Test locally first to isolate the issue

### Agent too slow?
- Try a faster model: `llama-3.1-8b-instant`
- Set `GROQ_MODEL` environment variable in Vercel

### Rate limit exceeded?
- Free tier: 30 requests/minute
- Wait a minute and try again
- Or contact Groq for higher limits

## Important Notes

⚠️ **File Storage**: The current app uses local files which won't persist on Vercel's serverless functions. For production:
- Use a database (PostgreSQL, MongoDB, Supabase)
- Or use Vercel Blob Storage
- Or use cloud storage (AWS S3, Google Cloud Storage)

This is fine for testing, but you'll need persistent storage for production use.

## Next Steps After Deployment

1. ✅ Test the deployment thoroughly
2. ✅ Configure proper authentication (replace name-based login with SSO)
3. ✅ Set up persistent storage for production
4. ✅ Add monitoring and error tracking
5. ✅ Configure custom domain (optional)

## Why Groq is Perfect for This

| Feature | Why It Matters |
|---------|---------------|
| **Serverless-ready** | Works perfectly on Vercel |
| **Fast inference** | Users get results quickly |
| **Free tier** | Test without cost |
| **No infrastructure** | No servers to manage |
| **Great models** | Llama 3.1 70B is very capable |

## Cost Estimate (After Beta)

Typical quote analysis:
- ~5,000 tokens per request
- ~$0.003 per analysis at expected pricing
- **Much cheaper than officer time** (saves 978 KES per quote!)

## Additional Help

- **Detailed Groq Setup**: See `GROQ_SETUP.md`
- **General Vercel Deployment**: See `VERCEL_DEPLOYMENT.md`
- **Groq Console**: https://console.groq.com
- **Vercel Dashboard**: https://vercel.com/dashboard
