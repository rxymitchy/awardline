# Groq API Setup Guide

## Why Groq?

Groq is the **best choice** for deploying Awardline to Vercel:

✅ **FREE** during beta period (no credit card required for testing)  
✅ **Super fast** - Up to 10x faster than OpenAI  
✅ **Great models** - Llama 3.1 70B, Mixtral, etc.  
✅ **OpenAI-compatible API** - Easy to integrate  
✅ **No local infrastructure** - Perfect for serverless deployment  

## Step 1: Get Your Groq API Key

1. Go to **https://console.groq.com**
2. Sign up or log in (free account)
3. Go to **API Keys** section
4. Click **"Create API Key"**
5. Copy your key (starts with `gsk_...`)

⚠️ **Save this key securely** - you won't be able to see it again!

## Step 2: Test Locally (Optional)

Before deploying to Vercel, test Groq locally:

```powershell
# Set your API key
$env:GROQ_API_KEY="gsk_your_key_here"

# Run the demo
.\.venv\Scripts\python -m awardline demo
```

The app will automatically use Groq if `GROQ_API_KEY` is set, otherwise it falls back to Ollama.

## Step 3: Deploy to Vercel

### Option A: Via Vercel Dashboard

1. Go to https://vercel.com/new
2. Import your GitHub repository: `rxymitchy/awardline`
3. Add environment variables:
   - **Name**: `GROQ_API_KEY`
   - **Value**: `gsk_your_key_here`
   - **Name**: `AWARDLINE_SECRET`
   - **Value**: Any random secure string
   - **Name**: `GROQ_MODEL` (optional)
   - **Value**: `llama-3.1-70b-versatile` (default)
4. Click **Deploy**

### Option B: Via Vercel CLI

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Add secrets
vercel secrets add groq-api-key "gsk_your_key_here"
vercel secrets add awardline-secret "your-secure-random-string"

# Deploy
vercel --prod
```

## Available Groq Models

Choose the best model for your needs:

| Model | Speed | Quality | Best For |
|-------|-------|---------|----------|
| `llama-3.1-70b-versatile` | Fast | Excellent | **Recommended** - Best balance |
| `llama-3.1-8b-instant` | Fastest | Good | Quick testing, cost-sensitive |
| `mixtral-8x7b-32768` | Fast | Great | Large context needs |
| `gemma2-9b-it` | Very Fast | Good | Speed-critical applications |

Set your preferred model in Vercel environment variables:
- **Variable**: `GROQ_MODEL`
- **Value**: Model name from table above

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `GROQ_API_KEY` | Yes | Your Groq API key | `gsk_abc123...` |
| `AWARDLINE_SECRET` | Yes | Session secret | `random-secure-string` |
| `GROQ_MODEL` | No | Model to use | `llama-3.1-70b-versatile` (default) |

## Rate Limits (Free Tier)

Groq's free tier includes:
- **Requests per minute**: 30
- **Requests per day**: 14,400
- **Tokens per minute**: 131,072

This is **more than enough** for testing and moderate production use.

## Cost Comparison (When Beta Ends)

Expected pricing after beta:

| Provider | Model | Cost per 1M tokens |
|----------|-------|-------------------|
| **Groq** | Llama 3.1 70B | ~$0.59 |
| OpenAI | GPT-4o | ~$2.50 |
| OpenAI | GPT-3.5 Turbo | ~$0.50 |
| Anthropic | Claude 3.5 Sonnet | ~$3.00 |

**Groq is 4-5x cheaper than competitors** while being significantly faster.

## Troubleshooting

### "GROQ_API_KEY environment variable is required"

**Solution**: Make sure you've added the environment variable in Vercel:
1. Go to your project in Vercel dashboard
2. Settings → Environment Variables
3. Add `GROQ_API_KEY` with your key
4. Redeploy the project

### "Rate limit exceeded"

**Solution**: 
- Free tier: 30 requests/minute
- Wait a minute and try again
- Or upgrade to paid tier for higher limits

### "Invalid API key"

**Solution**:
- Check that your key starts with `gsk_`
- Regenerate key at https://console.groq.com
- Update the key in Vercel environment variables
- Redeploy

### Agent still slow

**Solution**: Try a faster model:
- Set `GROQ_MODEL` to `llama-3.1-8b-instant`
- Or `gemma2-9b-it` for maximum speed

## Benefits Over Ollama

| Feature | Ollama (Local) | Groq (Cloud) |
|---------|---------------|--------------|
| Setup | Complex | Simple - just API key |
| Infrastructure | Requires server | Serverless |
| Speed | Depends on hardware | Very fast |
| Vercel Compatible | ❌ No (needs ngrok hack) | ✅ Yes |
| Cost | Free but needs server | Free tier + cheap paid |
| Maintenance | You manage updates | Managed for you |

## Next Steps

1. ✅ Get your Groq API key
2. ✅ Test locally (optional)
3. ✅ Add to Vercel environment variables
4. ✅ Deploy!

Your Awardline app will automatically use Groq and work perfectly on Vercel's serverless platform.

## Additional Resources

- [Groq Console](https://console.groq.com)
- [Groq Documentation](https://console.groq.com/docs)
- [Groq Pricing](https://wow.groq.com/pricing/)
- [Model Performance Benchmarks](https://wow.groq.com/)
