# 🚀 START HERE - Deploy Awardline to AWS

Welcome! This guide will help you deploy Awardline to AWS in 3 easy steps.

---

## ⚡ The Fastest Path (5 Minutes)

### Step 1: Install AWS CLI

**Windows:**
Download and install: https://awscli.amazonaws.com/AWSCLIV2.msi

**Linux/Mac:**
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

### Step 2: Configure AWS

```bash
aws configure
```

Enter:
- **Access Key ID**: (from AWS Console → IAM → Users → Security Credentials)
- **Secret Access Key**: (from AWS Console)
- **Region**: `eu-north-1`
- **Output format**: `json`

### Step 3: Deploy

**Windows (PowerShell):**
```powershell
.\Deploy-AwsEc2.ps1
```

**Linux/Mac:**
```bash
chmod +x aws-ec2-deploy.sh
./aws-ec2-deploy.sh
```

**Done!** Your app will be available at `http://<IP>` in ~15 minutes.

---

## 📚 Need More Help?

### If AWS CLI is not working:
→ Read **[SETUP_AWS_CLI.md](./SETUP_AWS_CLI.md)**

### If this is your first AWS deployment:
→ Read **[PRE_DEPLOYMENT_CHECKLIST.md](./PRE_DEPLOYMENT_CHECKLIST.md)**

### If you want to understand what's happening:
→ Read **[DEPLOY_NOW.md](./DEPLOY_NOW.md)**

### If you need complete documentation:
→ Read **[AWS_DEPLOYMENT.md](./AWS_DEPLOYMENT.md)**

### If you want to see all deployment files:
→ Read **[DEPLOYMENT_FILES_README.md](./DEPLOYMENT_FILES_README.md)**

---

## 🎯 What Gets Deployed

- **Application**: Awardline web interface
- **AI Model**: Qwen 2.5 3B via Ollama
- **Server**: EC2 t3.xlarge (4 vCPU, 16GB RAM)
- **Storage**: 50GB SSD
- **Region**: eu-north-1 (Stockholm)
- **Cost**: ~$4-5/day (~$130/month)

---

## ✅ Quick Checklist

Before running the deployment:

- [ ] AWS account active with credits for eu-north-1
- [ ] AWS CLI installed: `aws --version`
- [ ] AWS CLI configured: `aws sts get-caller-identity`
- [ ] In project directory: `cd awardline`

All good? Run the deployment script!

---

## 🎉 After Deployment

You'll see output like:
```
✓ Deployment Complete!
Instance ID: i-1234567890abcdef
Public IP: 13.51.XXX.XXX
Application URL: http://13.51.XXX.XXX
```

**Test it:**
1. Open the URL in your browser
2. Sign in with your name
3. Click "Check a Quote"
4. Enter test data and watch the agent work!

---

## 💡 Tips

- **First startup takes 15 minutes** (downloading AI model)
- **Stop instance when not using** to save money
- **Check deployment status**: SSH in and view logs
- **Full documentation** is in the markdown files

---

## 🆘 Something Wrong?

1. **Check AWS CLI**: `aws sts get-caller-identity`
2. **Verify region**: `aws configure get region` (should be `eu-north-1`)
3. **Wait longer**: Initial setup takes 15 minutes
4. **Check logs**: SSH into instance and view `/var/log/awardline-deployment.log`

Still stuck? See the troubleshooting section in **[AWS_DEPLOYMENT.md](./AWS_DEPLOYMENT.md)**.

---

## 📞 Get Help

- **Setup questions** → [SETUP_AWS_CLI.md](./SETUP_AWS_CLI.md)
- **Deployment questions** → [AWS_DEPLOYMENT.md](./AWS_DEPLOYMENT.md)
- **Application questions** → [README.md](./README.md)
- **GitHub Issues** → https://github.com/rxymitchy/awardline/issues

---

## 🚀 Ready? Let's Go!

```powershell
# Windows
.\Deploy-AwsEc2.ps1

# Linux/Mac
chmod +x aws-ec2-deploy.sh && ./aws-ec2-deploy.sh
```

Your Awardline deployment is just one command away! 🎉
