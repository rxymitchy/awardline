# 🚀 Quick Start: Deploy to Vercel in 5 Minutes

## Prerequisites
- GitHub account (you already have the code pushed)
- Free Groq account (we'll set this up)

---

## Step 1: Get Your Free Groq API Key (2 minutes)

1. Open: **https://console.groq.com**
2. Click **"Start Building"** or **"Sign In"**
3. Sign up with Google/GitHub (no credit card needed)
4. Once logged in, click **"API Keys"** in the left sidebar
5. Click **"Create API Key"**
6. Give it a name (e.g., "Awardline Production")
7. Click **"Submit"**
8. **Copy the key** - it starts with `gsk_`

⚠️ **Save this key somewhere safe** - you can't see it again!

---

## Step 2: Deploy to Vercel (3 minutes)

1. Open: **https://vercel.com/new**

2. **Import your repository**:
   - Click **"Import Git Repository"**
   - Find and select: `rxymitchy/awardline`
   - Click **"Import"**

3. **Configure the project**:
   - Project Name: `awardline` (or whatever you prefer)
   - Framework Preset: Leave as detected
   - Root Directory: `./` (leave default)

4. **Add Environment Variables** - Click "Add" for each:

   | Name | Value |
   |------|-------|
   | `GROQ_API_KEY` | Paste your `gsk_...` key from Step 1 |
   | `AWARDLINE_SECRET` | Type any random string (e.g., `my-secret-2024-xyz`) |
   | `GROQ_MODEL` | `llama-3.1-70b-versatile` |

5. Click **"Deploy"** button

6. Wait ~2-3 minutes for build to complete ⏱️

---

## Step 3: Test Your Deployment (1 minute)

Once deployed, Vercel shows your URL: `https://awardline-xxx.vercel.app`

1. Click the URL to open your app
2. You'll see the login page
3. Enter your name (e.g., "John Doe")
4. Click **"Check a quote"**
5. Fill in the form:
   - **Procuring entity**: `Nairobi City County`
   - **Purchase description**: `Office furniture`
   - **Quoted amount**: `500000`
   - **Supplier**: Leave blank or add one
6. Click **"Check quote"**
7. Watch the magic! 🎉
   - You'll see icons showing what the agent is doing
   - 🔍 Searching awards database
   - ⚖️ Comparing prices
   - ✍️ Writing committee note

---

## ✅ You're Done!

Your Awardline app is now:
- ✅ Live on the internet
- ✅ Using Groq's fast, free AI
- ✅ Running on Vercel's serverless platform
- ✅ Automatically deployed from GitHub

Every time you push to GitHub, Vercel will automatically redeploy!

---

## Troubleshooting

### "GROQ_API_KEY environment variable is required"
- Go to your Vercel project
- Click **Settings** → **Environment Variables**
- Make sure `GROQ_API_KEY` is added
- Click **"Redeploy"** at the top

### Build failed?
- Check the **Deployment** logs in Vercel dashboard
- Most common: Missing environment variable
- Click **"Redeploy"** after fixing

### Agent not working?
- Test your Groq API key at: https://console.groq.com
- Make sure it starts with `gsk_`
- Check you haven't hit rate limits (30/minute on free tier)

### Too slow?
- Change `GROQ_MODEL` to `llama-3.1-8b-instant` for faster (but slightly less accurate) results

---

## What's Next?

### For Testing
- ✅ You're all set! Start testing with real quotes

### For Production
See the full guides:
- **GROQ_SETUP.md** - Detailed Groq configuration
- **VERCEL_DEPLOYMENT.md** - Advanced Vercel options
- **README.md** - Full project documentation

Key production improvements:
1. Replace name-based login with proper SSO (Azure AD, Google Workspace)
2. Add persistent storage (database instead of local files)
3. Set up monitoring and alerts
4. Configure custom domain

---

## Quick Reference

**Your Deployment URL**: Check Vercel dashboard

**Groq Console**: https://console.groq.com (check usage, manage keys)

**Vercel Dashboard**: https://vercel.com/dashboard (manage deployments)

**GitHub Repo**: https://github.com/rxymitchy/awardline

---

## Free Tier Limits

### Groq (AI Model)
- ✅ 30 requests/minute
- ✅ 14,400 requests/day
- ✅ More than enough for testing!

### Vercel (Hosting)
- ✅ 100 GB bandwidth/month
- ✅ 100 hours serverless function execution
- ✅ Plenty for moderate use!

---

**Need help?** Check the troubleshooting guides or Groq/Vercel documentation.

🎉 **Congratulations - you just deployed an AI-powered procurement assistant!**
