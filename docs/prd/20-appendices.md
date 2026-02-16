
## 20. Appendices

### 20.1 Appendix A: X GraphQL API Details

The X GraphQL API uses these key endpoints:

```
POST https://x.com/i/api/graphql/{query_id}/TweetDetail
POST https://x.com/i/api/graphql/{query_id}/TweetResultByRestId
```

Query IDs change periodically. The baoyu-skills approach:
1. Maintains known query IDs in `constants.ts`
2. Falls back to scraping if queries fail

Our Python port will:
1. Store query IDs in config
2. Implement auto-discovery if needed
3. Fall back to Playwright

### 20.2 Appendix B: Substack Extraction

Substack articles are standard HTML with consistent structure:
- Title: `<h1 class="post-title">`
- Author: `<a class="author-name">`
- Content: `<div class="body markup">`

trafilatura handles this well. Edge cases:
- Paywalled content: Returns partial or error
- Images: Extracted with alt text

### 20.3 Appendix C: Whisper Model Comparison

| Model | Size | VRAM | Speed (M4) | Accuracy |
|-------|------|------|------------|----------|
| tiny | 75MB | ~1GB | ~0.5s/s | 85% |
| base | 142MB | ~1GB | ~1s/s | 90% |
| small | 466MB | ~2GB | ~2s/s | 93% |
| medium | 1.5GB | ~5GB | ~5s/s | 95% |
| large | 3GB | ~10GB | ~10s/s | 97% |

Selected: **small** - Best balance for 60s audio limit.

### 20.4 Appendix D: References

1. [OpenCode Documentation](https://opencode.ai/docs)
2. [OpenCode Server API](https://opencode.ai/docs/server)
3. [baoyu-skills X extractor](https://github.com/JimLiu/baoyu-skills)
4. [trafilatura documentation](https://trafilatura.readthedocs.io/)
5. [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
6. [Syncthing documentation](https://docs.syncthing.net/)
7. [Tailscale Funnel](https://tailscale.com/kb/1223/funnel)

---

**Document History**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-31 | Jarvis Team | Initial PRD |

---

**Approval**

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product Owner | | | |
| Tech Lead | | | |

---

Ready to proceed with implementation once approved. Do you want me to adjust any section or start building?