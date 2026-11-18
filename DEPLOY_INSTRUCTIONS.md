# Quick Deploy to Vercel - Step by Step

Your code is now on GitHub: https://github.com/rxymitchy/awardline

## Step 1: Connect to Vercel

1. Go to https://vercel.com/new
2. Click **"Import Git Repository"**
3. Select your GitHub repository: `rxymitchy/awardline`
4. Vercel will auto-detect it as a Python project

## Step 2: Configure Environment Variables

Before deploying, add these environment variables in the Vercel dashboard:

### Required Variables:

1. **AWARDLINE_SECRET**
   - Value: `your-secure-random-string-change-this-in-production`
   - Used for: Session management

2. **AWARDLINE_OLLAMA**
   - Value: Your Ollama server URL
   - Options:
     - Local with ngrok: `https://xxxx-xxx-xxx-xxx-xxx.ngrok-free.app`
     - Remote server: `https://your-ollama-server.com`
     - Or use OpenAI/Anthropic instead (see VERCEL_DEPLOYMENT.md)

3. **AWARDLINE_MODEL**
   - Value: `qwen2.5:3b` (or your preferred model)
   - Optional - defaults to `qwen2.5:3b`

## Step 3: Deploy

1. Click **"Deploy"**
2. Wait for the build to complete (2-3 minutes)
3. Vercel will give you a URL like: `https://awardline-xxxx.vercel.app`

## Step 4: Test the Deployment

1. Open your Vercel URL
2. Login with any name (e.g., "Test Officer")
3. Try submitting a quote
4. Watch the agent work with the enhanced UI showing process icons

## Important Notes

⚠️ **File Storage**: The current app uses local files which won't persist on Vercel's serverless functions. For production:
- Use a database (PostgreSQL, MongoDB)
- Or use Vercel Blob Storage
- Or use cloud storage (S3, GCS)

⚠️ **Ollama Connection**: Your Ollama instance must be accessible from the internet. Options:
- Use ngrok/cloudflare tunnel to expose local Ollama
- Deploy Ollama on a cloud server (AWS EC2, DigitalOcean, etc.)
- Switch to OpenAI/Anthropic API

## Quick Expose Local Ollama with ngrok

If you want to test with your local Ollama:

```bash
# Install ngrok: https://ngrok.com/download
# Then run:
ngrok http 11434
```

Copy the https URL (like `https://xxxx.ngrok-free.app`) and set it as `AWARDLINE_OLLAMA` in Vercel.

## Alternative: Deploy with Vercel CLI

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Deploy
vercel

# Add environment variables
vercel env add AWARDLINE_SECRET production
vercel env add AWARDLINE_OLLAMA production
vercel env add AWARDLINE_MODEL production

# Deploy to production
vercel --prod
```

## Troubleshooting

**Build fails?**
- Check Vercel build logs
- Ensure all dependencies in requirements.txt are compatible

**Agent not responding?**
- Verify AWARDLINE_OLLAMA URL is accessible
- Check that Ollama server has the model pulled
- Test the URL in your browser: `{AWARDLINE_OLLAMA}/api/tags`

**Files not saving?**
- Expected on Vercel - implement persistent storage solution
- See VERCEL_DEPLOYMENT.md for database integration options

## Next Steps

1. Configure proper authentication (SSO)
2. Set up persistent storage
3. Add monitoring and logging
4. Configure custom domain

For detailed deployment options and production considerations, see **VERCEL_DEPLOYMENT.md**
