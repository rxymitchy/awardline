# Vercel Deployment Guide

## Prerequisites

1. **Vercel Account**: Sign up at https://vercel.com
2. **GitHub Repository**: Push your code to GitHub
3. **Ollama Server**: You'll need Ollama accessible via public URL or use a cloud LLM service

## Deployment Options

### Option 1: Deploy with Remote Ollama (Recommended for testing)

If you have Ollama running on a server with a public URL:

1. **Connect GitHub to Vercel**:
   - Go to https://vercel.com/new
   - Import your GitHub repository
   - Vercel will auto-detect the Python project

2. **Configure Environment Variables** in Vercel Dashboard:
   - `AWARDLINE_SECRET`: A secure random string for session management
   - `AWARDLINE_OLLAMA`: Your Ollama server URL (e.g., `https://your-ollama-server.com`)
   - `AWARDLINE_MODEL`: `qwen2.5:3b` (or your preferred model)

3. **Deploy**: Click "Deploy" and Vercel will build and deploy your application

### Option 2: Use Cloud LLM Service (Recommended for production)

For production, consider using a cloud LLM API instead of Ollama:

**OpenAI:**
- Update `awardline/agent.py` to use OpenAI API
- Set `OPENAI_API_KEY` environment variable

**Anthropic Claude:**
- Update `awardline/agent.py` to use Anthropic API
- Set `ANTHROPIC_API_KEY` environment variable

### Option 3: Hybrid Deployment

Deploy web UI on Vercel, connect to local Ollama:

⚠️ **Note**: This requires exposing your local Ollama via tunnel (ngrok, cloudflare tunnel, etc.)

1. Expose local Ollama:
   ```bash
   # Using ngrok
   ngrok http 11434
   ```

2. Set `AWARDLINE_OLLAMA` to the tunnel URL in Vercel

3. Deploy as in Option 1

## Quick Deploy with Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Login to Vercel
vercel login

# Deploy
vercel

# Set environment variables
vercel env add AWARDLINE_SECRET
vercel env add AWARDLINE_OLLAMA
vercel env add AWARDLINE_MODEL

# Deploy to production
vercel --prod
```

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `AWARDLINE_SECRET` | Yes | Session secret key | `your-secure-random-string-here` |
| `AWARDLINE_OLLAMA` | Yes | Ollama server URL | `https://ollama.example.com` |
| `AWARDLINE_MODEL` | No | Model name | `qwen2.5:3b` (default) |

## Post-Deployment Checklist

- [ ] Test the login flow
- [ ] Submit a test quote and verify agent execution
- [ ] Check that files are saved correctly (may need persistent storage setup)
- [ ] Verify all static assets load correctly
- [ ] Test approval and filing workflow
- [ ] Monitor Vercel logs for errors

## Persistent Storage Considerations

⚠️ **Important**: Vercel functions are stateless. The current implementation stores data in local files:
- `runtime/flags/`
- `runtime/drafts/`
- `runtime/approvals/`
- `filings/`

**For production, you need to:**
1. Use a database (PostgreSQL, MongoDB, etc.) instead of file storage
2. Or use Vercel Blob/Storage for file persistence
3. Or use a cloud storage service (AWS S3, Google Cloud Storage)

## Troubleshooting

### Build Fails
- Check that all dependencies in `requirements.txt` are compatible with Vercel's Python runtime
- Review build logs in Vercel dashboard

### Agent Doesn't Respond
- Verify `AWARDLINE_OLLAMA` URL is accessible from Vercel's servers
- Check Ollama server logs
- Ensure the model is pulled on the Ollama server

### Files Not Persisting
- Implement persistent storage solution (see above)
- Files written during a request are lost when the function terminates

## Security Recommendations

1. **Use Vercel Secrets** for sensitive environment variables:
   ```bash
   vercel secrets add awardline-secret "your-secret-here"
   vercel secrets add awardline-ollama-url "https://ollama.example.com"
   ```

2. **Enable Authentication**: Replace name-based login with proper SSO (Azure AD, Google Workspace, etc.)

3. **Restrict API Access**: Add authentication middleware to protect API endpoints

4. **HTTPS Only**: Vercel provides HTTPS by default, but ensure no HTTP-only configurations

## Additional Resources

- [Vercel Python Runtime Documentation](https://vercel.com/docs/functions/serverless-functions/runtimes/python)
- [Vercel Environment Variables](https://vercel.com/docs/concepts/projects/environment-variables)
- [Vercel CLI Reference](https://vercel.com/docs/cli)
